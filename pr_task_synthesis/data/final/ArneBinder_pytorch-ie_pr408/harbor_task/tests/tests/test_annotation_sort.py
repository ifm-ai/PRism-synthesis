"""Test for Annotation sorting behavior."""
import dataclasses
from typing import Optional

import pytest

from pytorch_ie.core.document import Annotation


def test_annotation_sort():
    @dataclasses.dataclass(eq=True, frozen=True)
    class Dummy(Annotation):
        a: int
        b: Optional[int] = None
        c: int = 0

    dummy1 = Dummy(a=1, c=2)
    dummy2 = Dummy(a=1, c=3)
    dummy3 = Dummy(a=2, c=1)
    dummy4 = Dummy(a=2, c=2)

    assert sorted([dummy1, dummy2, dummy3, dummy4]) == [dummy1, dummy2, dummy3, dummy4]

    @dataclasses.dataclass(eq=True, frozen=True)
    class DummyWithNestedAnnotation(Annotation):
        a: int
        n: Dummy

    dummy_nested1 = DummyWithNestedAnnotation(a=1, n=Dummy(a=1, c=2))
    dummy_nested2 = DummyWithNestedAnnotation(a=2, n=Dummy(a=2, c=3))
    dummy_nested3 = DummyWithNestedAnnotation(a=2, n=Dummy(a=1, c=4))
    dummy_nested4 = DummyWithNestedAnnotation(a=1, n=Dummy(a=2, c=2))

    assert sorted([dummy_nested1, dummy_nested2, dummy_nested3, dummy_nested4]) == [
        dummy_nested1,
        dummy_nested4,
        dummy_nested3,
        dummy_nested2,
    ]

    with pytest.raises(ValueError) as excinfo:
        sorted([dummy1, dummy_nested1])
    assert (
        str(excinfo.value) == "comparison field names do not match: ['a', 'n'] != ['a', 'b', 'c']"
    )
