from threading import local

from flask import Flask

from app.utils import locale


def test_requests_without_a_supported_language_use_english():
    app = Flask(__name__)
    for headers in ({}, {'Accept-Language': 'unknown'}):
        with app.test_request_context(headers=headers):
            assert locale.get_locale() == 'en'
            assert locale.t('api.requireFileUpload') == 'Please upload at least one document file'
            assert 'English' in locale.get_language_instruction()


def test_explicit_chinese_choice_is_preserved():
    with Flask(__name__).test_request_context(headers={'Accept-Language': 'zh'}):
        assert locale.get_locale() == 'zh'
        assert locale.t('api.requireFileUpload') != 'Please upload at least one document file'


def test_background_threads_default_to_english_but_honor_explicit_locale(monkeypatch):
    monkeypatch.setattr(locale, '_thread_local', local())
    assert locale.get_locale() == 'en'
    locale.set_locale('zh')
    assert locale.get_locale() == 'zh'
