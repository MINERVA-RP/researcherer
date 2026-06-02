"""ID parsing is pure and network-free — exhaustively table-tested."""

import pytest

from researcherer.arxiv import parse_arxiv_id


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://arxiv.org/abs/2301.12345", ("2301.12345", None)),
        ("https://arxiv.org/abs/2301.12345v2", ("2301.12345", "2")),
        ("https://arxiv.org/pdf/2301.12345", ("2301.12345", None)),
        ("https://arxiv.org/pdf/2301.12345v3.pdf", ("2301.12345", "3")),
        ("arxiv.org/abs/1706.03762", ("1706.03762", None)),
        ("2301.12345", ("2301.12345", None)),
        ("2301.12345v2", ("2301.12345", "2")),
        ("1706.03762v7", ("1706.03762", "7")),
        # 5-digit serial (post-2015 high-volume months).
        ("https://arxiv.org/abs/2310.01234", ("2310.01234", None)),
        # Old-style identifiers.
        ("https://arxiv.org/abs/math/0309136", ("math/0309136", None)),
        ("math/0309136", ("math/0309136", None)),
        ("https://arxiv.org/abs/cond-mat.stat-mech/0309136",
         ("cond-mat.stat-mech/0309136", None)),
        ("hep-th/9901001v2", ("hep-th/9901001", "2")),
    ],
)
def test_parse_arxiv_id(text, expected):
    assert parse_arxiv_id(text) == expected


def test_parse_arxiv_id_rejects_garbage():
    with pytest.raises(ValueError):
        parse_arxiv_id("https://example.com/not-a-paper")
