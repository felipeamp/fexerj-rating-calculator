"""Read tournament data from Swiss Manager binary (.TUNX) files."""
import struct
import warnings

BIO_MARKER = bytes.fromhex("a5ff8944")
PAIRING_MARKER = bytes.fromhex("b3ff8944")
BYE_SNR = 0xFFFE
PAIRING_STRIDE = 21
RESULT_WIN = 1
RESULT_DRAW = 2
RESULT_LOSS = 3
KNOWN_RESULT_CODES = {0, 1, 2, 3, 4, 5, 6, 7, 9}
UNKNOWN_RESULT_THRESHOLD = 0.05  # flag if >5% of records have unknown result codes


def read_field(data, offset):
    """Read a [uint16 char_count][utf16-le chars] field. Returns (text, next_offset)."""
    char_count = struct.unpack_from('<H', data, offset)[0]
    offset += 2
    text = data[offset:offset + char_count * 2].decode('utf-16-le')
    return text, offset + char_count * 2


def skip_null(data, offset):
    """Advance past a UTF-16 null terminator (00 00) if present."""
    if offset + 1 < len(data) and data[offset] == 0 and data[offset + 1] == 0:
        return offset + 2
    return offset


def is_printable_utf16(data, offset, char_count):
    """Return True if char_count UTF-16-LE chars starting at offset are all printable Latin."""
    for i in range(char_count):
        pos = offset + i * 2
        if pos + 1 >= len(data):
            return False
        lo, hi = data[pos], data[pos + 1]
        if hi > 0x02 or (hi == 0 and lo < 0x20):
            return False
    return True


def skip_to_binary_block(data, pos, bio_end, min_zeros=8):
    """Advance pos until a run of at least min_zeros consecutive zero bytes
    is found, indicating the end of optional text fields and the start of
    the binary numeric padding that precedes each player's data block.
    """
    while pos < bio_end - min_zeros:
        if all(b == 0 for b in data[pos:pos + min_zeros]):
            return pos
        pos += 1
    return bio_end


def find_next_record(data, pos, bio_end):
    """Scan forward from pos for the start of the next player bio record.

    A record start must have two consecutive non-empty printable UTF-16 name
    fields (the first-name and last-name fields). This requirement rules out
    single-field optional entries like 'NAT' or 'U18' that end after one
    field.
    """
    while pos < bio_end - 10:
        n1 = struct.unpack_from('<H', data, pos)[0]
        if 1 <= n1 <= 40 and is_printable_utf16(data, pos + 2, n1):
            end1 = pos + 2 + n1 * 2
            if end1 + 2 <= bio_end:
                n2 = struct.unpack_from('<H', data, end1)[0]
                if 1 <= n2 <= 50 and is_printable_utf16(data, end1 + 2, n2):
                    return pos
        pos += 1
    return bio_end


def validate(filepath, data, bio, games):
    """Check format invariants and raise or warn if they are violated.

    Critical (raises ValueError):
      - Required section markers missing
      - No players parsed from bio section

    Warning (prints to stderr via warnings.warn):
      - Pairing section size not a multiple of the stride
      - More than 5% of pairing records have unknown result codes
      - Game records reference SNRs not present in the bio section
    """
    issues = []

    if BIO_MARKER not in data:
        raise ValueError(f"{filepath}: bio marker (a5ff8944) not found — unsupported format")
    if PAIRING_MARKER not in data:
        raise ValueError(f"{filepath}: pairing marker (b3ff8944) not found — unsupported format")
    if not bio:
        raise ValueError(f"{filepath}: no players parsed from bio section — unsupported format")

    # Pairing section boundaries (same logic as parse_pairing_section)
    pairing_start = data.find(PAIRING_MARKER) + 4
    pairing_end = len(data)
    for marker_hex in ("b5ff8944", "d3ff8944", "e3ff8944"):
        pos = data.find(bytes.fromhex(marker_hex))
        if pos != -1:
            pairing_end = min(pairing_end, pos)

    section_size = pairing_end - pairing_start
    if section_size % PAIRING_STRIDE != 0:
        issues.append(
            f"pairing section size {section_size} is not a multiple of stride {PAIRING_STRIDE}"
        )

    total_records = section_size // PAIRING_STRIDE
    unknown_count = 0
    pos = pairing_start
    while pos + PAIRING_STRIDE <= pairing_end:
        _, _, result = struct.unpack_from('<HHH', data, pos)
        pos += PAIRING_STRIDE
        if result not in KNOWN_RESULT_CODES:
            unknown_count += 1
    if total_records > 0 and unknown_count / total_records > UNKNOWN_RESULT_THRESHOLD:
        issues.append(
            f"{unknown_count}/{total_records} pairing records have unknown result codes "
            f"— stride or section boundaries may have changed"
        )

    valid_snrs = set(bio.keys())
    out_of_range = {snr for a, b, _ in games for snr in (a, b) if snr not in valid_snrs}
    if out_of_range:
        issues.append(f"game records reference unknown SNRs: {sorted(out_of_range)}")

    for issue in issues:
        warnings.warn(f"{filepath}: {issue}", UserWarning, stacklevel=3)


def parse_tunx(filepath):
    """Parse a Swiss Manager .TUNX binary file.

    Returns:
        bio (dict): {snr: {'name': str, 'fexerj_id': str}}
            where snr is the starting rank (1-based) and 'name' is
            formatted as 'Last, First'.
        games (list): [(snr_a, snr_b, score_for_a), ...]
            score_for_a is 1.0 (win), 0.5 (draw), or 0.0 (loss).
            Bye and forfeit results are excluded.

    Raises:
        ValueError: if critical format invariants are violated (missing markers,
            no players parsed, or too many unknown result codes).
    """
    with open(filepath, 'rb') as f:
        data = f.read()
    bio = parse_bio_section(data)
    games = parse_pairing_section(data)
    validate(filepath, data, bio, games)
    return bio, games


def parse_bio_section(data):
    bio_start = data.find(BIO_MARKER) + 4
    bio_end = data.find(PAIRING_MARKER)

    bio = {}
    snr = 1
    offset = bio_start
    while offset < bio_end - 4:
        try:
            first, offset = read_field(data, offset)
            last, offset = read_field(data, offset)
            offset = skip_null(data, offset)
            # Some records have a 1-char '*' field before the abbreviation; skip it
            if offset + 4 <= bio_end and struct.unpack_from('<H', data, offset)[0] == 1 and data[offset + 2:offset + 4] == b'\x2a\x00':
                offset += 4
            _abbrev, offset = read_field(data, offset)   # no null after abbrev
            _title, offset = read_field(data, offset)    # no null after title (empty for non-titled players)
            player_id, offset = read_field(data, offset)
            offset = skip_null(data, offset)
            offset += 4                          # 4-byte numeric padding
            club, offset = read_field(data, offset)
            fed, offset = read_field(data, offset)
            offset = skip_null(data, offset)    # fed may or may not carry a null
        except (struct.error, UnicodeDecodeError):
            break

        name = f"{last}, {first}" if last else first
        bio[snr] = {'name': name, 'fexerj_id': player_id}
        snr += 1

        # Jump past optional text fields (categories, FIDE, NAT, etc.) to
        # the zero-padded binary block, then locate the next record start.
        offset = skip_to_binary_block(data, offset, bio_end)
        next_start = find_next_record(data, offset, bio_end)
        if next_start >= bio_end:
            break
        offset = next_start

    return bio


def parse_pairing_section(data):
    pairing_start = data.find(PAIRING_MARKER) + 4
    pairing_end = len(data)
    for marker_hex in ("b5ff8944", "d3ff8944", "e3ff8944"):
        pos = data.find(bytes.fromhex(marker_hex))
        if pos != -1:
            pairing_end = min(pairing_end, pos)

    games = []
    pos = pairing_start
    while pos + PAIRING_STRIDE <= pairing_end:
        snr_a, snr_b, result = struct.unpack_from('<HHH', data, pos)
        pos += PAIRING_STRIDE
        if snr_a == 0 or snr_b == BYE_SNR or snr_b == 0:
            continue
        if result == RESULT_WIN:
            games.append((snr_a, snr_b, 1.0))
        elif result == RESULT_DRAW:
            games.append((snr_a, snr_b, 0.5))
        elif result == RESULT_LOSS:
            games.append((snr_a, snr_b, 0.0))

    return games
