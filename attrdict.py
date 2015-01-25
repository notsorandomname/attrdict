import collections
import functools

from restricted_object import create_restricted_object_cls

NO_VALUE = object()

# class PathTuple(tuple):
#     """
#     Sequence of keys in AttrDict.
#     """
#     def __new__(cls, *args):
#         if len(args) == 1 and isinstance(args[0], basestring):
#             args = [args[0].split('.')]
#         return super(PathTuple, cls).__new__(cls, *args)

# def path_as_argument_wrapper(method):
#     @functools.wraps(method)
#     def wrapper(self, key, *args, **kwargs):
#         if isinstance(key, PathTuple):
#             path = key
#         else:
#             path = PathTuple([key])
#         return method(self, path, *args, **kwargs)
#     return wrapper


class PathTypeError(TypeError):
    pass


class PathKeyError(KeyError):
    pass


def check_path_wrapper(func):
    @functools.wraps(func)
    def wrapper(self, path, *args, **kwargs):
        self._check_path(path)
        return func(self, path, *args, **kwargs)
    return wrapper


def set_exception_full_path_wrapper(func):
    @functools.wraps(func)
    def wrapper(self, path, *args, **kwargs):
        try:
            result = func(self, path, *args, **kwargs)
        except (PathKeyError, PathTypeError), exc:
            exc[1]['full_path'] = path
            raise
        return result
    return wrapper


def path_wrapper(func):
    return check_path_wrapper(
           set_exception_full_path_wrapper(
               func
            ))


_restricted_object_cls = create_restricted_object_cls(
        dont_override_methods=['__setattr__', '__getattribute__'])


class PathFunctor(_restricted_object_cls):
    __slots__ = ['__path', '__path_func', '__no_path_func', '__obj']

    def __init__(self, obj, path_func, no_path_func=None, allow_setattr=False):
        self.__path_func = path_func
        self.__no_path_func = no_path_func
        self.__path = []
        self.__obj = obj
        self.__allow_setattr = allow_setattr

    def __call__(self, *args, **kwargs):
        if not self.__path:
            if self.__no_path_func is None:
                # TODO: More meaningful message
                raise TypeError("This function doesn't support calling without path")
            # We are called like: x.func('test')
            result = getattr(self.__obj, self.__no_path_func)(*args, **kwargs)
        else:
            # We are called like: x.func.y.z('test'), inject path
            result = getattr(self.__obj, self.__path_func)(tuple(self.__path), *args, **kwargs)
        return result

    def __getitem__(self, key):
        self.__path.append(key)
        return self

    def __getattr__(self, attr):
        if attr.startswith('_'):
            raise AttributeError(attr)
        return self[attr]

    def __setattr__(self, attr, value):
        if attr.startswith('_'):
            return super(PathFunctor, self).__setattr__(attr, value)
        else:
            if not self.__allow_setattr:
                message = "%s doesn't support setattr magic syntax" % str(
                    self.__path_func
                )
                self._access_violation(
                    '__setattr__', attr, value,
                    message=message)
            self[attr](value)

    def __repr__(self, *args, **kwargs):
        if self.__path:
            self._access_violation('__repr__', *args, **kwargs)
        return self.__get_representation()

    def __get_representation(self):
        path_func_repr = repr(getattr(self.__obj, self.__path_func))
        no_path_func_repr = ''
        if self.no_path_func is not None:
            no_path_func_repr = repr(getattr(self.__obj, self.__no_path_func))
        return '<PathFunctor around %s%s>' % (
            path_func_repr,
            (' and %s' % no_path_func_repr if no_path_func_repr else '')
        )

    def __str__(self, *args, **kwargs):
        return repr(self)

    def _access_violation(self, method_name, *args, **kwargs):
        my_repr = self.__get_representation()
        raise TypeError(
            "While accessing the following method of %s" % my_repr,
            method_name, args, kwargs)


def path_functor_wrapper(*args, **kwargs):
    class FuncDescriptor(object):
        def __get__(self, obj, type=None):
            # XXX: Classmethods?
            return PathFunctor(obj, *args, **kwargs)

        def __set__(self, obj, value):
            # TODO: Better message
            raise TypeError("using setattr syntax without path")
    return FuncDescriptor()


class AttrDict(collections.MutableMapping):
    def __init__(self, *args, **kwargs):
        self._dict = {}
        other = dict(*args, **kwargs)
        for k, v in other.iteritems():
            self[k] = v

    # Methods required for ABC

    def __setitem__(self, key, value):
        assert value is not NO_VALUE, repr(key)
        if isinstance(value, collections.Mapping):
            # Convert mapping into an object of same class
            value = self.__class__(value)
        self._dict[key] = value

    def __getitem__(self, key):
        return self._dict[key]

    def __delitem__(self, key):
        del self._dict[key]

    def __len__(self):
        return len(self._dict)

    def __iter__(self):
        return iter(self._dict)

    def __getattr__(self, attr):
        value = self.get(attr, NO_VALUE)
        if value is NO_VALUE:
            raise AttributeError(attr)
        return value

    def __setattr__(self, attr, value):
        if attr.startswith('_'):
            super(AttrDict, self).__setattr__(attr, value)
        else:
            self[attr] = value

    def __repr__(self, *args, **kwargs):
        result = '{class_name}({representation})'.format(
            class_name=self.__class__.__name__,
            representation=repr(self._dict),
        )
        return result

    def _get_mapping(self, path):
        """
        Get mapping at path `path`

        If it meets not a mapping on its way, a PathTypeError is raised
        """
        self._check_path(path, allow_empty=True)
        mapping = self
        for i, path_element in enumerate(path):
            if path_element not in mapping:
                raise PathKeyError(
                    path_element,
                    dict(
                        path=path[:i],
                        full_path=path,
                    )
                )
            mapping = mapping[path_element]
            if not isinstance(mapping, collections.Mapping):
                raise PathTypeError(
                    "expected mapping, got %s instead" % repr(type(mapping)),
                    dict(
                        path=path[:i],
                        key=path_element,
                        full_path=path
                    )
                )
        return mapping

    def _get_or_create_mapping(self, path):
        try:
            mapping = self._get_mapping(path)
        except PathKeyError:
            mapping = self
            for path_element in path:
                if path_element not in mapping:
                    mapping[path_element] = {}
                mapping = mapping[path_element]
        return mapping

    @classmethod
    def _check_path(self, path, allow_empty=False):
        if not allow_empty:
            if not path:
                raise ValueError("path is empty")
        if not isinstance(path, (tuple, list)):
            raise TypeError(
                "expected tuple or list, got %s instead"
                % repr(type(path)))
        # Assert that all elements are hashable,
        # this allows us to be somewhat sure that there
        # will be no half-done set operations
        for i, path_element in enumerate(path):
            hash(path_element)

    # XXX: check_exist?
    @path_wrapper
    def get_path(self, path, default=None):
        mapping = self._get_mapping(path[:-1])
        return mapping.get(path[-1], default)

    @path_wrapper
    def set_path(self, path, value):
        mapping = self._get_or_create_mapping(path[:-1])
        mapping[path[-1]] = value

    @path_wrapper
    def setdefault_path(self, path, value=None):
        mapping = self._get_or_create_mapping(path[:-1])
        return mapping.setdefault(path[-1], value)

    @path_wrapper
    def pop_path(self, path, default=NO_VALUE):
        branch, key = path[:-1], path[-1]
        try:
            mapping = self._get_mapping(branch)
        except PathKeyError:
            if default is NO_VALUE:
                raise
            else:
                return default
        if default is NO_VALUE:
            try:
                result = mapping.pop(key)
            except KeyError:
                raise PathKeyError(
                    key,
                    dict(
                        path=path[:-1],
                        full_path=path,
                    )
                )
        else:
            result = mapping.pop(key, default)
        return result

    @path_wrapper
    def has_path(self, path):
        return self.get_path(path, NO_VALUE) is not NO_VALUE

    def _real_get(self, *args, **kwargs):
        return super(AttrDict, self).get(*args, **kwargs)

    def _real_setdefault(self, *args, **kwargs):
        return super(AttrDict, self).setdefault(*args, **kwargs)

    def _real_pop(self, *args, **kwargs):
        return super(AttrDict, self).pop(*args, **kwargs)

    def _real_has(self, key):
        return key in self

    get = path_functor_wrapper('get_path', no_path_func='_real_get')
    setdefault = path_functor_wrapper('setdefault_path',
                                      no_path_func='_real_setdefault')
    pop = path_functor_wrapper('pop_path', no_path_func='_real_pop')
    set = path_functor_wrapper('set_path', allow_setattr=True)
    has = path_functor_wrapper('has_path', no_path_func='_real_has')

    def _merge(self, other):
        return merge(self, other)

    def _inplace_merge(self, other):
        return inplace_merge(self, other)


def merge(left, right):
    "return a new dictionary which is a recursively merged left and right"
    return generic_merge(type(left)(left), right, merge)


def inplace_merge(left, right):
    "inplace recursive merge two dictionaties"
    return generic_merge(left, right, inplace_merge)


class MergeError(ValueError):
    "error raised when two values can't be merged"


def generic_merge(left, right, merge_function):
    "merge `left` and `right`, using `merge_function` for merging mappings"
    for key, right_value in right.iteritems():
        value = right_value
        if key in left:
            left_value = left[key]
            left_is_mapping = isinstance(left_value, collections.Mapping)
            right_is_mapping = isinstance(right_value, collections.Mapping)
            if left_is_mapping and right_is_mapping:
                value = merge_function(left_value, right_value)
            elif left_is_mapping ^ right_is_mapping:
                raise MergeError(
                    left_value, right_value,
                    dict(message="Can't merge value with a mapping"))
        left[key] = value
    return left

GET = 'get'
SET = 'set'
DEL = 'del'


def _get_action(name):
    return ('__dict%s__' % name, '__%sitem__' % name)

DESCRIPTOR_ACTIONS = {}
for _action in [GET, SET, DEL]:
    DESCRIPTOR_ACTIONS[_action] = _get_action(_action)
del _action


class TypedAttrDict(AttrDict):
    """AttrDict for which you can define sort of "schema" """
    def _get_descriptor(self, key):
        descriptor = getattr(type(self), key,  NO_VALUE)
        if descriptor is NO_VALUE:
            raise KeyError(key)
        return descriptor

    def _action_func(self, action, key, *args, **kwargs):
        descriptor = self._get_descriptor(key)
        descr_action, dict_action = DESCRIPTOR_ACTIONS[action]
        descr_func = getattr(descriptor, descr_action, NO_VALUE)
        if descr_func is NO_VALUE:
            return getattr(super(TypedAttrDict, self), dict_action)(key, *args, **kwargs)
        else:
            return descr_func(self, key, *args, **kwargs)

    def __getitem__(self, key):
        return self._action_func(GET, key)

    def __setitem__(self, key, value):
        self._action_func(SET, key, value)

    def __delitem__(self, key):
        self._action_func(DEL, key)
