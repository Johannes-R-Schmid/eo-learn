"""
A simple feature extraction module. The notation is from Hollstein [1].

The grammar of the language:

E -> T | T;E
T -> I(T,T) | S(T,T) | D(T,T,T) | R(T,T) | B
B -> B01 | B02 | B03 | ... | B12

[1] http://www.mdpi.com/2072-4292/8/8/666
"""
# pylint: disable=invalid-name
from eolearn.core import EOTask, FeatureType

import numpy as np
import logging

LOGGER = logging.getLogger(__name__)


class Lexer(list):
    def skip_whitespace(self):
        while self[0].isspace():
            self.popleft()

    def popleft(self):
        return self.pop(0)

    def next(self):
        self.skip_whitespace()
        return self.popleft()

    def peek(self):
        self.skip_whitespace()
        return self[0]


class FeatureExtendedExtractor:
    def __init__(self, expr):
        self.parsed = self.parse_E(Lexer(expr))

    def __call__(self, x):
        return [f(x) for f in self.parsed]

    @staticmethod
    def ensure_follows(lexer, expected_ch):
        ch = lexer.next()
        if ch != expected_ch:
            raise SyntaxError("Expected '{}', got '{}'".format(expected_ch, ch))

    def parse_E(self, lexer):
        vals = [self.parse_T(lexer)]

        while lexer:
            FeatureExtendedExtractor.ensure_follows(lexer, ';')
            vals.append(self.parse_T(lexer))

        return vals

    def parse_T(self, lexer):
        ch = lexer.next()
        return {
            'I': self.parse_I,
            'S': self.parse_S,
            'R': self.parse_R,
            'D': self.parse_D,
            'B': self.parse_B
        }[ch](lexer)

    def parse_I(self, lexer):
        FeatureExtendedExtractor.ensure_follows(lexer, '(')
        val_fst = self.parse_T(lexer)
        FeatureExtendedExtractor.ensure_follows(lexer, ',')
        val_snd = self.parse_T(lexer)
        FeatureExtendedExtractor.ensure_follows(lexer, ')')

        def _index_fun(x):
            v1 = val_fst(x)
            v2 = val_snd(x)
            return (v1 - v2) / (v1 + v2)

        return _index_fun

    def parse_S(self, lexer):
        FeatureExtendedExtractor.ensure_follows(lexer, '(')
        val_fst = self.parse_T(lexer)
        FeatureExtendedExtractor.ensure_follows(lexer, ',')
        val_snd = self.parse_T(lexer)
        FeatureExtendedExtractor.ensure_follows(lexer, ')')

        return lambda x: val_fst(x) - val_snd(x)

    def parse_R(self, lexer):
        FeatureExtendedExtractor.ensure_follows(lexer, '(')
        val_fst = self.parse_T(lexer)
        FeatureExtendedExtractor.ensure_follows(lexer, ',')
        val_snd = self.parse_T(lexer)
        FeatureExtendedExtractor.ensure_follows(lexer, ')')

        return lambda x: val_fst(x) / val_snd(x)

    def parse_D(self, lexer):
        FeatureExtendedExtractor.ensure_follows(lexer, '(')
        val_fst = self.parse_T(lexer)
        FeatureExtendedExtractor.ensure_follows(lexer, ',')
        val_snd = self.parse_T(lexer)
        FeatureExtendedExtractor.ensure_follows(lexer, ',')
        val_thd = self.parse_T(lexer)
        FeatureExtendedExtractor.ensure_follows(lexer, ')')

        return lambda x: (val_fst(x) + val_snd(x)) / val_thd(x)

    @staticmethod
    def parse_B(lexer):
        num = lexer.next()
        nxt = lexer.peek()
        if nxt.isdigit():
            lexer.popleft()
            return lambda x: x[10 * int(num) + int(nxt)]
        if nxt.lower() == 'a':
            lexer.popleft()
            return lambda x: x[8]
        nr = int(num) - 1
        return lambda x: x[nr if nr < 8 else nr + 1]


class FeatureExtractionTask(EOTask):
    def __init__(self, expr, source_field, target_field):
        self.fee = FeatureExtendedExtractor(expr)
        self.src_field = source_field
        self.tgt_field = target_field

    def execute(self, eopatch):
        shp = eopatch.data[self.src_field].shape

        LOGGER.debug("Input array shape: %s", shp)

        value = np.apply_along_axis(lambda x: np.asarray(self.fee(x)), arr=eopatch.data[self.src_field],
                                    axis=len(shp)-1)

        LOGGER.debug("Feature array shape: %s", value.shape)

        eopatch.add_feature(attr_type=FeatureType.DATA, field=self.tgt_field, value=value)

        return eopatch
