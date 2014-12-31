
import pytest
from mock import MagicMock

from attrdict import (
    AttrDict as AD, PathTypeError, PathKeyError,
    path_functor_wrapper
)


def test_empty_dict():
    assert AD() == {}


def test_update_like_behaviour():
    assert AD(a=1, b=2) == {'a': 1, 'b': 2}


def test_update_from_dict():
    assert AD({'a': 1, 'b': 2}) == {'a': 1, 'b': 2}


def test_update_dict_is_copied():
    x = {'a': 1, 'b': 2}
    y = AD(x)
    x['a'] = 3
    assert x != y


def test_update_dict_attrdict_is_copied():
    x = AD({'a': 1, 'b': 2})
    y = AD(x)
    y['a'] = 3
    assert x != y


def test_setitem_dict_is_copied():
    x = AD()
    y = AD(a=1)
    x['dict'] = y
    y['b'] = 2
    assert x['dict'] != y


def test_setattr_sets_item():
    x = AD()
    x.element = 1
    assert x['element'] == 1


def test_getattr_gets_item():
    x = AD(element=1)
    assert x.element == 1


def test_getattr_raises_attribute_error():
    x = AD(element=1)
    with pytest.raises(AttributeError) as exc_info:
        x.unknown
    assert 'unknown' == exc_info.value[0]


def test_repr():
    x = AD(element=1)
    assert repr(x) == str(x) == "AttrDict({'element': 1})"


def test_get_mapping_empty():
    x = AD(element=1)
    assert x._get_mapping(tuple()) is x


def test_get_mapping_depth_1():
    x = AD(root=AD(leaf=1))
    assert x._get_mapping(tuple(['root'])) is x.root


def test_get_mapping_depth_2():
    x = AD(root=AD(branch=AD(leaf=1)))
    assert x._get_mapping(tuple(['root', 'branch'])) is x.root.branch


def assert_path_not_a_mapping_error(exc_info, path, key, full_path):
    exc = exc_info.value
    details = exc[1]
    assert details['path'] == path
    assert details['key'] == key
    assert details['full_path'] == full_path
    assert ('expected mapping, got %s instead' % repr(int)) in exc[0]


def test_get_mapping_not_a_mapping():
    x = AD(root=1)
    with pytest.raises(PathTypeError) as exc_info:
        x._get_mapping(tuple(['root']))
    assert_path_not_a_mapping_error(
        exc_info, path=(), key='root', full_path=('root',)
    )


def test_get_mapping_not_a_mapping_depth_2():
    x = AD(root=AD(leaf=1))
    with pytest.raises(PathTypeError) as exc_info:
        x._get_mapping(tuple(['root', 'leaf']))
    assert_path_not_a_mapping_error(
        exc_info, path=('root',), key='leaf', full_path=('root', 'leaf')
    )


def assert_path_key_error(exc_info, key, path, full_path):
    exc = exc_info.value
    details = exc[1]
    assert details['path'] == path
    assert details['full_path'] == full_path
    assert exc[0] == key


def test_get_mapping_key_error():
    x = AD()
    path = tuple(['unknown'])
    with pytest.raises(PathKeyError) as exc_info:
        x._get_mapping(path)
    assert_path_key_error(exc_info, 'unknown', path=(), full_path=path)


def test_get_mapping_key_error_depth_2():
    x = AD(root=AD(leaf=1))
    path = tuple(['root', 'unknown'])
    with pytest.raises(PathKeyError) as exc_info:
        x._get_mapping(path)
    assert_path_key_error(exc_info, 'unknown', path=('root',), full_path=path)


def test_get_or_create_mapping_acts_as_get():
    x = AD(root=AD(leaf=1))
    assert x._get_or_create_mapping(('root',)) is x.root


def test_get_or_create_mapping_creates_attrdict():
    x = AD()
    m = x._get_or_create_mapping(('root', 'branch'))
    assert x.root.branch is m
    assert isinstance(m, type(x))


def test_get_or_create_mapping_fails_to_create_attrdict():
    x = AD(root=AD(branch=1))
    path = ('root', 'branch')
    with pytest.raises(TypeError) as exc_info:
        x._get_or_create_mapping(path)
    assert_path_not_a_mapping_error(
        exc_info, path=('root',), key='branch', full_path=('root', 'branch')
    )


def test_get_path_depth_1():
    x = AD(element=1)
    assert x.get_path(('element',)) == 1


def test_get_path_depth_1_default():
    x = AD(element=1)
    assert x.get_path(('unknown',), 1) == 1


def test_get_path_depth_2():
    x = AD(root=AD(leaf=1))
    assert x.get_path(('root', 'leaf')) == 1


def test_get_path_depth_2_default():
    x = AD(root=AD(leaf=1))
    assert x.get_path(('root', 'unknown'), 1) == 1


def test_get_path_returns_none_on_default():
    x = AD()
    assert x.get_path(('unknown',)) is None


@pytest.mark.parametrize("func,additional_args", [
    ("get_path", []),
    ("set_path", [42]),
    ("setdefault_path", [42]),
    (("pop_path", [42])),
])
def test_empty_path_raises_value_error(func, additional_args):
    x = AD(value=1)
    with pytest.raises(ValueError) as exc_info:
        getattr(x, func)(tuple(), *additional_args)
    assert 'path is empty' == exc_info.value[0]


def test_check_path_not_a_tuple():
    with pytest.raises(TypeError) as exc_info:
        AD._check_path(42)
    assert 'expected tuple or list, got %s instead' % repr(int) in str(exc_info)


def test_check_path_empty_tuple():
    with pytest.raises(ValueError) as exc_info:
        AD._check_path(())
    assert 'path is empty' in str(exc_info)


def test_check_path_empty_tuple_allow_empty():
    AD._check_path((), allow_empty=True)


def test_check_path_unhashable():
    with pytest.raises(TypeError):
        AD._check_path(('a', 'b', []))


@pytest.mark.parametrize("method", ['set_path', 'setdefault_path'])
def test_set_path(method):
    x = AD()
    getattr(x, method)(('root',), 5)
    assert x.root == 5


@pytest.mark.parametrize("method", ['set_path', 'setdefault_path'])
def test_set_path_depth_2(method):
    x = AD()
    getattr(x, method)(('root', 'leaf'), 5)
    assert x.root.leaf == 5


@pytest.mark.parametrize("method", ['set_path', 'setdefault_path'])
def test_set_path_existing_non_branch(method):
    x = AD(root=AD(branch=1))
    path = ('root', 'branch', 'leaf')
    with pytest.raises(TypeError) as exc_info:
        getattr(x, method)(('root', 'branch', 'leaf'), 2)
    assert_path_not_a_mapping_error(
        exc_info, path=('root',), key='branch', full_path=path
    )


@pytest.mark.parametrize("method", ['set_path', 'setdefault_path'])
def test_set_path_depth_existing_branch(method):
    x = AD(root=AD(branch=AD(leaf=1)))
    getattr(x, method)(('root', 'branch', 'another'), 2)
    assert x.root.branch.another == 2


def test_set_path_changes_existing_value():
    x = AD(root=AD(leaf=1))
    x.set_path(('root', 'leaf'), 2)
    assert x.root.leaf == 2


def test_setdefault_path_doesnt_change_existing_value():
    x = AD(root=AD(leaf=1))
    x.setdefault_path(('root', 'leaf'), 2)
    assert x.root.leaf == 1


def test_setdefault_path_returns_current_value():
    x = AD(root=AD(leaf=1))
    assert x.setdefault_path(('root', 'leaf'), 2) == 1


def test_setdefault_path_sets_none_on_default():
    x = AD()
    assert x.setdefault_path(('unknown',)) is None
    assert x.unknown is None


def test_pop_path_simple():
    x = AD(root=1)
    assert x.pop_path(('root',)) == 1
    assert x == AD()


def test_pop_path_non_existing_raises_key_error():
    x = AD(root=1)
    y = AD(x)
    with pytest.raises(PathKeyError) as exc_info:
        x.pop_path(('unknown',))
    assert x == y
    assert_path_key_error(exc_info, 'unknown', path=(), full_path=('unknown',))


def test_pop_path_non_existing_returns_default_value():
    x = AD(root=1)
    y = AD(x)
    assert x.pop_path(('unknown',), 42) == 42
    assert x == y


def test_pop_path_non_existing_depth_2_raises_key_error():
    x = AD(root=AD(leaf=1))
    y = AD(x)
    path = ('root', 'branch')
    with pytest.raises(PathKeyError) as exc_info:
        x.pop_path(('root', 'branch'))
    assert x == y
    assert_path_key_error(exc_info, 'branch', path=('root',), full_path=path)


def test_pop_path_non_existing_depth_2_returns_default_value():
    x = AD(root=AD(leaf=1))
    y = AD(x)
    assert x.pop_path(('root', 'branch'), 42) == 42
    assert x == y


def test_pop_path_non_existing_intermediate_branch_raises_key_error():
    x = AD(root=AD(branch=AD(leaf=1)))
    y = AD(x)
    path = ('root', 'unknown', 'leaf')
    with pytest.raises(PathKeyError) as exc_info:
        x.pop_path(path)
    assert x == y
    assert_path_key_error(exc_info, 'unknown', path=('root',), full_path=path)


def test_pop_path_non_existing_intermediate_branch_returns_default_value():
    x = AD(root=AD(branch=AD(leaf=1)))
    y = AD(x)
    assert x.pop_path(('root', 'unknown', 'leaf'), 42) == 42
    assert x == y

def test_magic_syntax_get():
    x = AD(root=AD(branch=AD(leaf=1)))
    assert x.get.root() is x.root

def test_magic_syntax_get_default_none():
    x = AD(root=AD(branch=AD(leaf=1)))
    assert x.get.root.unknown() == None

def test_magic_syntax_get_default():
    x = AD(root=AD(branch=AD(leaf=1)))
    assert x.get.root.unknown('default') == 'default'

def test_magic_syntax_set_setattr():
    x = AD(root=1)
    x.set.another = 1
    assert x == AD(root=1, another=1)

def test_magic_syntax_set_setattr_depth():
    x = AD(root=1)
    x.set.another.one = 1
    assert x == AD(root=1, another=AD(one=1))

@pytest.fixture
def magic_obj():
    class MagicObject(object):
        def path_func(self, path, *args, **kwargs):
            return path, args, kwargs
        def no_path_func(self, *args, **kwargs):
            return args, kwargs
        func = path_functor_wrapper('path_func', 'no_path_func')
        only_path_func = path_functor_wrapper('path_func')
        setattr_func = path_functor_wrapper('path_func', allow_setattr=True)
    return MagicObject()

class TestAttributePathAccessWrapper(object):
    def test_path_func(self, magic_obj):
        assert magic_obj.func.root.leaf.branch(4, b=51) == (('root', 'leaf', 'branch'), (4,), dict(b=51))

    def test_raises_attribute_error_on_underscore_attributes(self):
        with pytest.raises(AttributeError) as exc_info:
            magic_obj._unknown
        assert '_unknown' in exc_info.exconly()

    def test_no_path_func(self, magic_obj):
        assert magic_obj.func(1, 2, k=3) == ((1, 2), dict(k=3))

    def test_only_path_func_raises_type_error(self, magic_obj):
        with pytest.raises(TypeError) as exc_info:
            assert magic_obj.only_path_func(1, 2)

    def test_only_path_func_works_with_path(self, magic_obj):
        assert magic_obj.only_path_func.root.leaf(1, 2) == (('root', 'leaf'), (1, 2), {})

    def test_setattr(self, magic_obj):
        magic_obj.path_func = MagicMock()
        magic_obj.setattr_func.root.leaf = 1
        magic_obj.path_func.assert_called_with(('root', 'leaf'), 1)

    def test_setattr_without_path_raises_type_error(self, magic_obj):
        magic_obj.path_func = MagicMock()
        with pytest.raises(TypeError):
            magic_obj.setattr_func = 1

    def test_path_func_faulty_code_raises_type_error(self, magic_obj):
        with pytest.raises(TypeError):
            magic_obj.func.a.b + 1

    def test_using_same_descriptor_twice(self, magic_obj):
        assert magic_obj.func.root() == (('root',), (), {})
        assert magic_obj.func.another() == (('another',), (), {})