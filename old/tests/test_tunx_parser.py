"""Unit tests for tunx_parser module."""
import pathlib
import struct
import warnings
import pytest

from tunx_parser import (
    _read_field,
    _skip_null,
    _is_printable_utf16,
    _skip_to_binary_block,
    _find_next_record,
    _parse_bio_section,
    _validate,
    parse_tunx,
    _BIO_MARKER,
    _PAIRING_MARKER,
    _BYE_SNR,
)

_BINARY_DIR = pathlib.Path(__file__).parent / 'binary'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utf16_field(text):
    """Encode text as a [uint16 char_count][utf16-le chars] field."""
    encoded = text.encode('utf-16-le')
    return struct.pack('<H', len(text)) + encoded


# ---------------------------------------------------------------------------
# _read_field
# ---------------------------------------------------------------------------

class TestReadField:
    def test_reads_simple_ascii(self):
        data = _utf16_field("Silva")
        text, offset = _read_field(data, 0)
        assert text == "Silva"
        assert offset == len(data)

    def test_reads_empty_string(self):
        data = _utf16_field("")
        text, offset = _read_field(data, 0)
        assert text == ""
        assert offset == 2

    def test_reads_accented_characters(self):
        data = _utf16_field("Hervé")
        text, _ = _read_field(data, 0)
        assert text == "Hervé"

    def test_reads_at_nonzero_offset(self):
        prefix = b'\xff\xff'
        data = prefix + _utf16_field("Jose")
        text, offset = _read_field(data, 2)
        assert text == "Jose"
        assert offset == 2 + 2 + 8  # prefix + char_count + 4 chars * 2 bytes


# ---------------------------------------------------------------------------
# _skip_null
# ---------------------------------------------------------------------------

class TestSkipNull:
    def test_skips_null_terminator(self):
        data = b'\x00\x00\xAB\xCD'
        assert _skip_null(data, 0) == 2

    def test_no_null_returns_same_offset(self):
        data = b'\x41\x00\xAB\xCD'
        assert _skip_null(data, 0) == 0

    def test_only_first_byte_zero_no_skip(self):
        data = b'\x00\x41'
        assert _skip_null(data, 0) == 0

    def test_at_end_of_data_no_skip(self):
        data = b'\x00'
        assert _skip_null(data, 0) == 0


# ---------------------------------------------------------------------------
# _is_printable_utf16
# ---------------------------------------------------------------------------

class TestIsPrintableUtf16:
    def test_printable_ascii_chars(self):
        data = "Hello".encode('utf-16-le')
        assert _is_printable_utf16(data, 0, 5) is True

    def test_control_character_not_printable(self):
        # 0x0009 = TAB (hi=0, lo=0x09 < 0x20)
        data = struct.pack('<H', 0x0009)
        assert _is_printable_utf16(data, 0, 1) is False

    def test_high_unicode_not_printable(self):
        # 0x0410 = Cyrillic А (hi=0x04 > 0x02)
        data = struct.pack('<H', 0x0410)
        assert _is_printable_utf16(data, 0, 1) is False

    def test_latin_extended_printable(self):
        # 0x00E9 = é (hi=0x00, lo=0xE9 >= 0x20)
        data = struct.pack('<H', 0x00E9)
        assert _is_printable_utf16(data, 0, 1) is True

    def test_zero_char_count_returns_true(self):
        assert _is_printable_utf16(b'', 0, 0) is True

    def test_out_of_bounds_returns_false(self):
        data = b'\x41'  # only 1 byte, but need 2 for one UTF-16 char
        assert _is_printable_utf16(data, 0, 1) is False


# ---------------------------------------------------------------------------
# _skip_to_binary_block
# ---------------------------------------------------------------------------

class TestSkipToBinaryBlock:
    def test_finds_zero_run(self):
        data = b'\x01\x02\x03' + b'\x00' * 8 + b'\xFF'
        assert _skip_to_binary_block(data, 0, len(data)) == 3

    def test_already_at_zero_run(self):
        data = b'\x00' * 8 + b'\xFF'
        assert _skip_to_binary_block(data, 0, len(data)) == 0

    def test_returns_bio_end_if_no_run_found(self):
        data = b'\x01\x02\x03\x04\x05'
        assert _skip_to_binary_block(data, 0, len(data)) == len(data)

    def test_short_zero_run_not_enough(self):
        # 4-zero run is skipped; 8-zero run (followed by a non-zero byte) is found at offset 6
        data = b'\x01' + b'\x00' * 4 + b'\x01' + b'\x00' * 8 + b'\xFF'
        assert _skip_to_binary_block(data, 0, len(data)) == 6


# ---------------------------------------------------------------------------
# _find_next_record
# ---------------------------------------------------------------------------

class TestFindNextRecord:
    def _make_two_fields(self, first, last):
        return _utf16_field(first) + _utf16_field(last)

    def test_finds_valid_two_field_record(self):
        data = self._make_two_fields("Jose", "Silva")
        assert _find_next_record(data, 0, len(data)) == 0

    def test_skips_single_field_entry(self):
        # Single field "NAT" followed by empty second field — should not match
        single = _utf16_field("NAT") + _utf16_field("")
        two_field = self._make_two_fields("Jose", "Silva")
        data = single + two_field
        assert _find_next_record(data, 0, len(data)) == len(single)

    def test_returns_bio_end_when_no_record(self):
        data = b'\x00' * 20
        assert _find_next_record(data, 0, len(data)) == len(data)

    def test_skips_nonprintable_bytes(self):
        garbage = b'\xFF\xFF\x00\x00'
        valid = self._make_two_fields("Ana", "Lima")
        data = garbage + valid
        assert _find_next_record(data, 0, len(data)) == len(garbage)


# ---------------------------------------------------------------------------
# _parse_bio_section
# ---------------------------------------------------------------------------

def _make_player_bytes(first, last, abbrev, title, player_id, club, fed, asterisk_prefix=False):
    """Build a minimal bio record in Swiss Manager binary format."""
    record = _utf16_field(first) + _utf16_field(last)
    if asterisk_prefix:
        record += _utf16_field('*')           # 1-char marker; no null after last name
    else:
        record += b'\x00\x00'                 # null separator after last name
    record += _utf16_field(abbrev)
    record += _utf16_field(title)
    record += _utf16_field(player_id)
    record += b'\x00\x00'                     # null after player_id
    record += b'\x00\x00\x00\x00'            # 4-byte numeric padding
    record += _utf16_field(club)
    record += _utf16_field(fed)
    record += b'\x00\x00'                     # null after fed
    record += b'\x00' * 40                    # binary block (triggers _skip_to_binary_block)
    return record


class TestParseBioSection:
    def _wrap(self, player_bytes):
        """Wrap player bytes in BIO/PAIRING markers so _parse_bio_section can find them."""
        return _BIO_MARKER + player_bytes + _PAIRING_MARKER

    def test_normal_record_parsed(self):
        data = self._wrap(_make_player_bytes('Jose', 'Silva', 'J. Jose', '', '1234', 'Clube', 'BRA'))
        bio = _parse_bio_section(data)
        assert len(bio) == 1
        assert bio[1]['fexerj_id'] == '1234'
        assert bio[1]['name'] == 'Silva, Jose'

    def test_asterisk_prefix_record_parsed(self):
        data = self._wrap(_make_player_bytes('Leandro', 'Vieira', 'L. Leandro', '', '5523', 'Clube', 'BRA', asterisk_prefix=True))
        bio = _parse_bio_section(data)
        assert len(bio) == 1
        assert bio[1]['fexerj_id'] == '5523'

    def test_asterisk_and_normal_records_both_parsed(self):
        player1 = _make_player_bytes('Ivan', 'Frolov', 'F. Ivan', '', '5221', 'Cmun', 'RUS')
        player2 = _make_player_bytes('Leandro', 'Vieira', 'L. Leandro', '', '5523', 'Cfcsn', 'BRA', asterisk_prefix=True)
        data = self._wrap(player1 + player2)
        bio = _parse_bio_section(data)
        assert len(bio) == 2
        assert bio[1]['fexerj_id'] == '5221'
        assert bio[2]['fexerj_id'] == '5523'


# ---------------------------------------------------------------------------
# _validate
# ---------------------------------------------------------------------------

def _minimal_data(bio_marker=True, pairing_marker=True):
    """Construct a minimal valid binary blob with the required section markers."""
    data = b'\x00' * 100
    if bio_marker:
        data = _BIO_MARKER + data
    if pairing_marker:
        data = data + _PAIRING_MARKER + b'\x00' * 21
    return data


class TestValidate:
    def test_missing_bio_marker_raises(self):
        data = _PAIRING_MARKER + b'\x00' * 100
        with pytest.raises(ValueError, match="bio marker"):
            _validate("test.TUNX", data, {1: {'name': 'A', 'fexerj_id': ''}}, [])

    def test_missing_pairing_marker_raises(self):
        data = _BIO_MARKER + b'\x00' * 100
        with pytest.raises(ValueError, match="pairing marker"):
            _validate("test.TUNX", data, {1: {'name': 'A', 'fexerj_id': ''}}, [])

    def test_empty_bio_raises(self):
        data = _BIO_MARKER + b'\x00' * 50 + _PAIRING_MARKER + b'\x00' * 50
        with pytest.raises(ValueError, match="no players"):
            _validate("test.TUNX", data, {}, [])

    def test_unknown_result_codes_warn(self):
        # Build a pairing section with a single record whose result code is 0xFF (unknown)
        pairing_record = struct.pack('<HHH', 1, 2, 0xFF) + b'\x00' * 15
        data = _BIO_MARKER + b'\x00' * 10 + _PAIRING_MARKER + pairing_record
        bio = {1: {'name': 'A', 'fexerj_id': ''}, 2: {'name': 'B', 'fexerj_id': ''}}
        with pytest.warns(UserWarning, match="unknown result codes"):
            _validate("test.TUNX", data, bio, [])

    def test_out_of_range_snr_warns(self):
        pairing_record = struct.pack('<HHH', 1, 2, 1) + b'\x00' * 15
        data = _BIO_MARKER + b'\x00' * 10 + _PAIRING_MARKER + pairing_record
        bio = {1: {'name': 'A', 'fexerj_id': ''}}  # SNR 2 is missing from bio
        with pytest.warns(UserWarning, match="unknown SNRs"):
            _validate("test.TUNX", data, bio, [(1, 2, 1.0)])

    def test_valid_data_raises_nothing(self):
        pairing_record = struct.pack('<HHH', 1, 2, 1) + b'\x00' * 15
        data = _BIO_MARKER + b'\x00' * 10 + _PAIRING_MARKER + pairing_record
        bio = {1: {'name': 'A', 'fexerj_id': ''}, 2: {'name': 'B', 'fexerj_id': ''}}
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            _validate("test.TUNX", data, bio, [(1, 2, 1.0)])  # must not raise


# ---------------------------------------------------------------------------
# parse_tunx — integration tests against real binary files
# ---------------------------------------------------------------------------

TUNX_T1  = str(_BINARY_DIR / 'swiss_system_18players.TUNX')
TURX_T6  = str(_BINARY_DIR / 'round_robin_6players.TURX')
TUMX_T8  = str(_BINARY_DIR / 'swiss_team_93players.TUMX')


class TestParseTunxIntegration:
    def test_t1_player_count(self):
        bio, _ = parse_tunx(TUNX_T1)
        assert len(bio) == 18

    def test_t1_known_fexerj_ids(self):
        bio, _ = parse_tunx(TUNX_T1)
        assert bio[1]['fexerj_id'] == '1078'   # Sergio (SNR 1)
        assert bio[11]['fexerj_id'] == '3128'  # Marques Kempel (SNR 11)

    def test_t1_snr18_has_no_id(self):
        bio, _ = parse_tunx(TUNX_T1)
        assert bio[18]['fexerj_id'] == ''      # Newton Gomes — not registered

    def test_t1_name_format(self):
        bio, _ = parse_tunx(TUNX_T1)
        # Names should be formatted as "Last, First"
        assert ',' in bio[1]['name']

    def test_t1_game_count(self):
        _, games = parse_tunx(TUNX_T1)
        # 18 players, 6 rounds; byes and forfeits excluded — verified against binary
        assert len(games) == 42

    def test_t1_total_points_equal_number_of_games(self):
        _, games = parse_tunx(TUNX_T1)
        # Each game distributes exactly 1.0 point total between both players
        total = sum(score + (1.0 - score) for _, _, score in games)
        assert abs(total - len(games)) < 0.001

    def test_t1_no_bye_in_games(self):
        _, games = parse_tunx(TUNX_T1)
        for snr_a, snr_b, _ in games:
            assert snr_b != _BYE_SNR
            assert snr_a != 0
            assert snr_b != 0

    def test_t1_scores_are_valid(self):
        _, games = parse_tunx(TUNX_T1)
        for _, _, score in games:
            assert score in (0.0, 0.5, 1.0)

    def test_turx_t6_player_count(self):
        bio, _ = parse_tunx(TURX_T6)
        assert len(bio) == 6

    def test_turx_t6_all_ids_present(self):
        bio, _ = parse_tunx(TURX_T6)
        assert all(info['fexerj_id'] for info in bio.values())

    def test_tumx_t8_player_count(self):
        bio, _ = parse_tunx(TUMX_T8)
        assert len(bio) == 93

    def test_tumx_t8_scores_are_valid(self):
        _, games = parse_tunx(TUMX_T8)
        for _, _, score in games:
            assert score in (0.0, 0.5, 1.0)

    def test_tumx_t8_no_bye_in_games(self):
        _, games = parse_tunx(TUMX_T8)
        for snr_a, snr_b, _ in games:
            assert snr_b != _BYE_SNR
            assert snr_a != 0
            assert snr_b != 0
