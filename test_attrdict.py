
import pytest
import mock
from mock import MagicMock, call

from attrdict import (
    AttrDict, PathTypeError, PathKeyError,
    path_functor_wrapper, merge, inplace_merge, generic_merge,
    MergeError
)

AD = AttrDict


@pytest.fixture
def ad1():
    return AD(root=1)


@pytest.fixture
def ad2():
    return AD(root=AD(leaf=2))


@pytest.fixture
def ad3():
    return AD(root=AD(branch=AD(leaf=3)))


class TestBasicProperties(object):
    def test_empty_dict(self):
        assert AD() == {}

    def test_update_like_behaviour(self):
        assert AD(a=1, b=2) == {'a': 1, 'b': 2}

    def test_update_from_dict(self):
        assert AD({'a': 1, 'b': 2}) == {'a': 1, 'b': 2}

    def test_setattr_sets_item(self):
        x = AD()
        x.element = 1
        assert x['element'] == 1

    def test_getattr_gets_item(self):
        x = AD(element=1)
        assert x.element == 1

    def test_getattr_raises_attribute_error(self):
        x = AD(element=1)
        with pytest.raises(AttributeError) as exc_info:
            x.unknown
        assert 'unknown' == exc_info.value[0]

    @pytest.mark.parametrize('value,length', [
        ({}, 0),
        ({'a': 1}, 1),
        ({'a': {'b': 2}}, 1),
        ({'a': 1, 'z': {'b': 2}, 'c': 3}, 3)
    ])
    def test_len(self, value, length):
        assert len(AD(value)) == length

    def test_repr(self):
        x = AD(element=1)
        assert repr(x) == str(x) == "AttrDict({'element': 1})"

    # Test that AttrDict doesn't share subdicts with another AttrDicts

    def test_update_dict_is_copied(self):
        x = {'a': 1, 'b': 2}
        y = AD(x)
        x['a'] = 3
        assert x != y

    def test_update_dict_attrdict_is_copied(self):
        x = AD({'a': 1, 'b': 2})
        y = AD(x)
        y['a'] = 3
        assert x != y

    def test_setitem_dict_is_copied(self):
        x = AD()
        y = AD(a=1)
        x['dict'] = y
        y['b'] = 2
        assert x['dict'] != y


def assert_path_not_a_mapping_error(exc_info, path, key, full_path):
    exc = exc_info.value
    details = exc[1]
    assert details['path'] == path
    assert details['key'] == key
    assert details['full_path'] == full_path
    assert ('expected mapping, got %s instead' % repr(int)) in exc[0]


def assert_path_key_error(exc_info, key, path, full_path):
    exc = exc_info.value
    details = exc[1]
    assert details['path'] == path
    assert details['full_path'] == full_path
    assert exc[0] == key


class TestGetMapping(object):
    def test_get_mapping_empty(self):
        x = AD(element=1)
        assert x._get_mapping(tuple()) is x

    def test_get_mapping_depth_1(self, ad2):
        assert ad2._get_mapping(tuple(['root'])) is ad2.root

    def test_get_mapping_depth_2(self, ad3):
        assert ad3._get_mapping(tuple(['root', 'branch'])) is ad3.root.branch

    def test_get_mapping_not_a_mapping(self, ad1):
        with pytest.raises(PathTypeError) as exc_info:
            ad1._get_mapping(tuple(['root']))
        assert_path_not_a_mapping_error(
            exc_info, path=(), key='root', full_path=('root',)
        )

    def test_get_mapping_not_a_mapping_depth_2(self, ad2):
        with pytest.raises(PathTypeError) as exc_info:
            ad2._get_mapping(tuple(['root', 'leaf']))
        assert_path_not_a_mapping_error(
            exc_info, path=('root',), key='leaf', full_path=('root', 'leaf')
        )

    def test_get_mapping_key_error(self, ad1):
        path = tuple(['unknown'])
        with pytest.raises(PathKeyError) as exc_info:
            ad1._get_mapping(path)
        assert_path_key_error(exc_info, 'unknown', path=(), full_path=path)

    def test_get_mapping_key_error_depth_2(self, ad2):
        path = tuple(['root', 'unknown'])
        with pytest.raises(PathKeyError) as exc_info:
            ad2._get_mapping(path)
        assert_path_key_error(exc_info, 'unknown',
                              path=('root',), full_path=path)

    def test_get_or_create_mapping_acts_as_get(self, ad2):
        assert ad2._get_or_create_mapping(('root',)) is ad2.root

    def test_get_or_create_mapping_creates_attrdict(self):
        x = AD()
        m = x._get_or_create_mapping(('root', 'branch'))
        assert x.root.branch is m
        assert isinstance(m, type(x))

    def test_get_or_create_mapping_fails_to_create_attrdict(self, ad2):
        path = ('root', 'leaf')
        with pytest.raises(TypeError) as exc_info:
            ad2._get_or_create_mapping(path)
        assert_path_not_a_mapping_error(
            exc_info, path=('root',),
            key='leaf', full_path=('root', 'leaf')
        )


class TestGetPath(object):
    def test_depth_1(self, ad1):
        assert ad1.get_path(('root',)) == 1

    def test_depth_1_default(self, ad1):
        assert ad1.get_path(('unknown',), 'default') == 'default'

    def test_depth_2(self, ad2):
        assert ad2.get_path(('root', 'leaf')) == 2

    def test_depth_2_default(self, ad2):
        assert ad2.get_path(('root', 'unknown'), 'default') == 'default'

    def test_depth_3(self, ad3):
        assert ad3.get_path(('root', 'branch', 'leaf')) == 3

    def test_depth_1_none_on_default(self, ad1):
        assert ad1.get_path(('unknown',)) is None

    def test_depth_2_none_on_default(self, ad2):
        assert ad2.get_path(('root', 'unknown')) is None


class CheckPathCalled(Exception):
    pass


class TestCheckPath(object):
    all_methods_decorator = pytest.mark.parametrize("func,additional_args", [
        ("get_path", []),
        ("set_path", [42]),
        ("setdefault_path", [42]),
        ("pop_path", [42]),
        ("has_path", []),
    ])

    @all_methods_decorator
    def test_check_path_called(self, ad1, func, additional_args):
        with mock.patch('attrdict.AttrDict._check_path') as patched_check_path:
            patched_check_path.side_effect = CheckPathCalled()
            with pytest.raises(CheckPathCalled):
                getattr(ad1, func)(None, *additional_args)

    def test_path_not_a_tuple(self):
        with pytest.raises(TypeError) as exc_info:
            AD._check_path(42)
        assert 'expected tuple or list, got %r instead' % int in str(exc_info)

    def test_path_empty_tuple(self):
        with pytest.raises(ValueError) as exc_info:
            AD._check_path(())
        assert 'path is empty' in str(exc_info)

    def test_path_empty_tuple_allow_empty(self):
        AD._check_path((), allow_empty=True)

    def test_path_unhashable(self):
        with pytest.raises(TypeError):
            AD._check_path(('a', 'b', []))


class TestSetPath(object):
    set_and_setdefault = pytest.mark.parametrize(
        "method", ['set_path', 'setdefault_path']
    )

    @set_and_setdefault
    def test_depth_1(self, method):
        x = AD()
        getattr(x, method)(('root',), 5)
        assert x.root == 5

    @set_and_setdefault
    def test_depth_2(self, method):
        x = AD()
        getattr(x, method)(('root', 'leaf'), 5)
        assert x.root.leaf == 5

    @set_and_setdefault
    def test_existing_non_branch(self, method, ad2):
        path = ('root', 'leaf', 'unknown')
        with pytest.raises(TypeError) as exc_info:
            getattr(ad2, method)(path, 2)
        assert_path_not_a_mapping_error(
            exc_info, path=('root',), key='leaf', full_path=path
        )

    @set_and_setdefault
    def test_depth_existing_branch(self, method, ad3):
        getattr(ad3, method)(('root', 'branch', 'another'), 2)
        assert ad3.root.branch.another == 2

    def test_set_changes_existing_value(self, ad2):
        ad2.set_path(('root', 'leaf'), 'new')
        assert ad2.root.leaf == 'new'

    def test_setdefault_doesnt_change_existing_value(self, ad2):
        ad2.setdefault_path(('root', 'leaf'), 42)
        assert ad2.root.leaf == 2

    def test_setdefault_returns_current_value(self, ad2):
        assert ad2.setdefault_path(('root', 'leaf'), 42) == 2

    def test_setdefault_sets_none_on_default(self):
        ad = AD()
        assert ad.setdefault_path(('unknown',)) is None
        assert ad.unknown is None

    def test_setdefault_sets_none_on_default_depth_2(self, ad2):
        assert ad2.setdefault_path(('root', 'unknown')) is None
        assert ad2.root.unknown is None

    def test_setdefault_doesnt_change_existing_value_on_default(self, ad2):
        assert ad2.setdefault_path(('root', 'leaf')) == 2
        assert ad2.root.leaf == 2


class TestPopPath(object):
    def test_existing_depth_1(self, ad1):
        assert ad1.pop_path(('root',)) == 1
        assert ad1 == AD()

    def test_existing_depth_2(self, ad2):
        assert ad2.pop_path(('root', 'leaf')) == 2
        assert ad2 == AD(root=AD())

    def test_non_existing_raises_key_error_depth_1(self, ad1):
        ad1_copy = AD(ad1)
        with pytest.raises(PathKeyError) as exc_info:
            ad1.pop_path(('unknown',))
        assert ad1 == ad1_copy
        assert_path_key_error(exc_info, 'unknown', path=(),
                              full_path=('unknown',))

    def test_non_existing_raises_key_error_depth_2(self, ad2):
        ad2_copy = AD(ad2)
        with pytest.raises(PathKeyError) as exc_info:
            ad2.pop_path(('root', 'unknown'))
        assert ad2 == ad2_copy
        assert_path_key_error(exc_info, 'unknown', path=('root',),
                              full_path=('root', 'unknown',))

    def test_non_existing_returns_default_value(self, ad1):
        ad1_copy = AD(ad1)
        assert ad1.pop_path(('unknown',), 42) == 42
        assert ad1 == ad1_copy

    def test_non_existing_depth_2_returns_default_value(self, ad2):
        ad2_copy = AD(ad2)
        assert ad2.pop_path(('root', 'unknown'), 42) == 42
        assert ad2 == ad2_copy

    def test_non_existing_intermediate_branch_raises_key_error(self, ad3):
        ad3_copy = AD(ad3)
        path = ('root', 'unknown', 'leaf')
        with pytest.raises(PathKeyError) as exc_info:
            ad3.pop_path(path)
        assert ad3 == ad3_copy
        assert_path_key_error(exc_info, 'unknown', path=('root',),
                              full_path=path)

    def test_non_existing_intermediate_branch_returns_default_value(self, ad3):
        ad3_copy = AD(ad3)
        assert ad3.pop_path(('root', 'unknown', 'leaf'), 42) == 42
        assert ad3 == ad3_copy


class TestHasPath(object):
    def test_depth_1_yes(self, ad1):
        assert ad1.has_path(('root',))

    def test_depth_1_no(self, ad1):
        assert not ad1.has_path(('unknown',))

    def test_depth_1_mapping_yes(self, ad2):
        assert ad2.has_path(('root',))

    def test_depth_2_yes(self, ad2):
        assert ad2.has_path(('root', 'leaf'))

    def test_depth_2_no(self, ad2):
        assert not ad2.has_path(('root', 'unknown'))


class TestMagicSyntax(object):
    def test_get(self, ad3):
        assert ad3.get.root() is ad3.root

    def test_get_default_none(self, ad3):
        assert ad3.get.root.unknown() is None

    def test_get_default(self, ad3):
        assert ad3.get.root.unknown('default') == 'default'

    def test_set_setattr(self, ad1):
        ad1.set.another = 1
        assert ad1 == AD(root=1, another=1)

    def test_set_setattr_depth(self, ad1):
        ad1.set.another.one = 1
        assert ad1 == AD(root=1, another=AD(one=1))

    def test_setdefault_no_setattr(self, ad1):
        with pytest.raises(TypeError):
            ad1.setdefault.root = 1

    def test_pop_depth_1(self, ad1):
        assert ad1.pop.root() == 1
        assert ad1 == AD()

    def test_pop_depth_2(self, ad2):
        assert ad2.pop.root.leaf() == 2
        assert ad2 == AD(root=AD())

    def test_usual_pop(self, ad1):
        assert ad1.pop('root') == 1
        assert ad1 == AD()

    def test_has(self, ad2):
        assert ad2.has.root.leaf()

    def test_not_has(self, ad2):
        assert not ad2.has.root.unknown()

    def test_usual_has(self, ad1):
        assert ad1.has('root')

    def test_common_error_forgotten_brackets(self, ad2):
        with pytest.raises(TypeError):
            assert ad2.pop.root.leaf == 2


class TestAttributePathAccessWrapper(object):
    @pytest.fixture
    def magic_obj(self):
        class MagicObject(object):
            path_func = MagicMock(return_value='path_func')
            no_path_func = MagicMock(return_value='no_path_func')

            func = path_functor_wrapper('path_func', 'no_path_func')
            only_path_func = path_functor_wrapper('path_func')
            setattr_func = path_functor_wrapper('path_func',
                                                allow_setattr=True)
        return MagicObject()

    def test_path_func(self, magic_obj):
        assert magic_obj.func.root.leaf.branch(4, b=51) == 'path_func'
        magic_obj.path_func.assert_called_with(
            ('root', 'leaf', 'branch'), 4, b=51)

    def test_raises_attribute_error_on_underscore_attributes(self, magic_obj):
        with pytest.raises(AttributeError) as exc_info:
            magic_obj.func._unknown
        assert '_unknown' in exc_info.exconly()

    def test_no_path_func(self, magic_obj):
        assert magic_obj.func(1, 2, k=3) == 'no_path_func'
        magic_obj.no_path_func.assert_called_with(1, 2, k=3)

    def test_only_path_func_raises_type_error(self, magic_obj):
        with pytest.raises(TypeError):
            assert magic_obj.only_path_func(1, 2)

    def test_only_path_func_works_with_path(self, magic_obj):
        assert magic_obj.only_path_func.root.leaf(1, 2) == 'path_func'
        magic_obj.path_func.assert_called_with(('root', 'leaf'), 1, 2)

    def test_setattr(self, magic_obj):
        magic_obj.setattr_func.root.leaf = 1
        magic_obj.path_func.assert_called_with(('root', 'leaf'), 1)

    def test_setattr_without_path_raises_type_error(self, magic_obj):
        with pytest.raises(TypeError):
            magic_obj.setattr_func = 1

    def test_no_setattr_raises_on_setattr(self, magic_obj):
        with pytest.raises(TypeError):
            magic_obj.func.some = 1

    def test_path_func_faulty_code_raises_type_error(self, magic_obj):
        with pytest.raises(TypeError):
            magic_obj.func.a.b + 1

    def test_using_same_descriptor_twice(self, magic_obj):
        magic_obj.func.root()
        magic_obj.path_func.assert_called_with(('root',))
        magic_obj.func.another()
        magic_obj.path_func.assert_called_with(('another',))

    def test_repr_should_not_raise_on_empty_path(self, magic_obj):
        assert 'PathFunctor' in repr(magic_obj.func)

    def test_repr_is_str(self, magic_obj):
        assert repr(magic_obj.func) == str(magic_obj.func)

    def test_repr_should_raise_on_empty_path(self, magic_obj):
        with pytest.raises(TypeError):
            repr(magic_obj.func.some)


class TestMerge(object):
    def cases():
        return pytest.mark.parametrize('left,right,expected', [
            [{}, {}, {}],
            [dict(x=1), dict(y=2), dict(x=1, y=2)],
            [dict(x=1, y=2), dict(y=42, z=3), dict(x=1, y=42, z=3)],
            [
                dict(x=1, y=dict(y1=1)), dict(y=dict(y2=1), z=3),
                dict(x=1, y=dict(y1=1, y2=1), z=3)
            ],
            [
                dict(x=dict(y=dict(z=1, h=4))), dict(x=dict(y=dict(z=2, w=3))),
                dict(x=dict(y=dict(z=2, w=3, h=4)))
            ]
        ])

    @cases()
    def test_merge(self, left, right, expected):
        assert merge(left, right) == expected

    @cases()
    def test_merge_doesnt_change_input_values(self, left, right, expected):
        left_copy = AD(left)
        right_copy = AD(right)
        merge(left, right)
        assert left == left_copy
        assert right == right_copy

    @cases()
    def test_inplace_merge(self, left, right, expected):
        result = inplace_merge(left, right)
        assert result == expected

    def test_inplace_merge_changes_left_element(self):
        left = AD(x=1)
        right = AD(y=2)
        assert inplace_merge(left, right) is left

    def test_attrdict_merge(self):
        left = AD(x=1)
        right = AD(y=2)
        assert left._merge(right) == merge(left, right)

    def test_attrdict_inplace_merge(self):
        left = AD(x=1)
        right = AD(y=2)
        left_copy = AD(left)
        right_copy = AD(right)
        assert (
            left._inplace_merge(right) ==
            inplace_merge(left_copy, right_copy)
        )
        assert left == left_copy

    def test_generic_merge(self):
        left = AD(x=1, y=AD(z=2), n=AD())
        right = AD(x=2, y=AD(z=3, w=4), n=AD(nn=5))
        merge_func = MagicMock(return_value='merged')
        result = generic_merge(left, right, merge_func)
        assert result == AD(x=2, y='merged', n='merged')
        merge_func.assert_has_calls([
            call(AD(z=2), AD(z=3, w=4)),
            call(AD(), AD(nn=5)),
        ], any_order=True)

    def test_cant_merge_mapping_with_value(self):
        left = AD(x=1)
        right = AD(x=AD(y=2))
        with pytest.raises(MergeError) as exc_info:
            merge(left, right)
        assert exc_info.value[:2] == (1, AD(y=2))
