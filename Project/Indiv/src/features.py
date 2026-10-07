"""Feature builders.

Every model in the ladder consumes a DataFrame with two text columns, so the
vectorisers are wired up with a ColumnTransformer rather than a bare
vectoriser. That keeps the choice visible: word features read the normalised
text, character features read the original.

Why character n-grams matter here: smishing obfuscates deliberately
(``acc0unt``, ``DB5``, ``bit.ly/xY2`` ) and word tokenisation destroys exactly
the evidence that gives it away. Character spans survive it.
"""

from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer

# The two columns produced by src.preprocess.
TEXT_CLEAN = "text_clean"  # normalised, placeholder tokens, lowercase
TEXT_RAW = "text"  # untouched: digits, case and punctuation intact


def word_features(ngram_range=(1, 2), min_df=2, max_features=50_000) -> ColumnTransformer:
    """Word-level TF-IDF over the normalised text. The baseline representation."""
    return ColumnTransformer(
        [
            (
                "word",
                TfidfVectorizer(
                    ngram_range=ngram_range,
                    min_df=min_df,
                    max_features=max_features,
                    sublinear_tf=True,
                ),
                TEXT_CLEAN,
            )
        ],
        remainder="drop",
    )


def char_features(ngram_range=(2, 5), min_df=2, max_features=100_000) -> ColumnTransformer:
    """Character n-grams over the *raw* text — the obfuscation handler."""
    return ColumnTransformer(
        [
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=ngram_range,
                    min_df=min_df,
                    max_features=max_features,
                    sublinear_tf=True,
                ),
                TEXT_RAW,
            )
        ],
        remainder="drop",
    )


def word_char_features() -> ColumnTransformer:
    """Both representations side by side, concatenated into one matrix."""
    return ColumnTransformer(
        [
            (
                "word",
                TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
                TEXT_CLEAN,
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True
                ),
                TEXT_RAW,
            ),
        ],
        remainder="drop",
    )


def count_features(ngram_range=(1, 1)) -> ColumnTransformer:
    """Raw counts for Naive Bayes, which assumes counts rather than TF-IDF."""
    from sklearn.feature_extraction.text import CountVectorizer

    return ColumnTransformer(
        [("word", CountVectorizer(ngram_range=ngram_range, min_df=1), TEXT_CLEAN)],
        remainder="drop",
    )
