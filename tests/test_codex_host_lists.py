from pathlib import Path


def test_bilingual_codex_host_lists_preserve_fork_policy():
    root = Path(__file__).resolve().parents[1]
    for name in ('README.md', 'README.en.md'):
        text = (root / name).read_text(encoding='utf-8')
        intro = text.splitlines()[12]
        assert 'Codex' in intro
        assert '~/.agents/skills/<slug>/' in text
        assert 'junction' in text
    index = (root / 'docs/index.md').read_text(encoding='utf-8')
    assert 'Codex' in index.split('---', 2)[1]
    assert not (root / 'README.ru.md').exists()
    assert not (root / 'README.zh-CN.md').exists()
