"""The languages offered for the outputs of an instruction template."""

from __future__ import annotations

from watch_me.core.languages import ALL_LANGUAGES, DEFAULT_LANGUAGE, TOP_LANGUAGES


def test_all_languages_are_sorted_unique_and_plain():
    assert list(ALL_LANGUAGES) == sorted(ALL_LANGUAGES)
    assert len(set(ALL_LANGUAGES)) == len(ALL_LANGUAGES)
    assert 170 <= len(ALL_LANGUAGES) <= 190
    assert all(name and name == name.strip() for name in ALL_LANGUAGES)
    assert not [name for name in ALL_LANGUAGES if ";" in name or "," in name]


def test_english_and_czech_are_on_top_and_in_the_full_list():
    assert TOP_LANGUAGES == ("English", "Czech")
    assert DEFAULT_LANGUAGE == "English"
    assert set(TOP_LANGUAGES) <= set(ALL_LANGUAGES)
    assert {"Spanish", "German", "Chinese", "Slovak"} <= set(ALL_LANGUAGES)
