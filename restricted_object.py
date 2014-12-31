methods = """
__abs__
__add__
__and__
# __bases__
__call__
# __class__
# __closure__
__cmp__
# __code__
__coerce__
__complex__
__contains__
# __defaults__
# Don't override __del__ because that may confuse gc
# __del__
__delattr__
__delete__
__delitem__
__delslice__
# __dict__
__div__
__divmod__
# __doc__
__enter__
__eq__
__exit__
# __file__
__float__
__floordiv__
# __func__
# __future__
__ge__
__get__
__getattr__
__getattribute__
__getitem__
__getslice__
# __globals__
__gt__
__hash__
__hex__
__iadd__
__iand__
__idiv__
__ifloordiv__
__ilshift__
__imod__
__imul__
__index__
# __init__
__instancecheck__
__int__
__invert__
__iop__
__ior__
__ipow__
__irshift__
__isub__
__iter__
__itruediv__
__ixor__
__le__
__len__
__long__
__lshift__
__lt__
# __metaclass__
__missing__
__mod__
# __module__
__mul__
# __name__
__ne__
__neg__
# __new__
__nonzero__
__oct__
__or__
__pos__
__pow__
__radd__
__rand__
__rcmp__
__rdiv__
__rdivmod__
__repr__
__reversed__
__rfloordiv__
__rlshift__
__rmod__
__rmul__
__ror__
__rpow__
__rrshift__
__rshift__
__rsub__
__rtruediv__
__rxor__
__self__
__set__
__setattr__
__setitem__
__setslice__
__slots__
__str__
__sub__
__subclasscheck__
__truediv__
__unicode__
__weakref__
__xor__
# Pickle special methods
__setstate__
__getstate__
__reduce__
__reduce_ex__
"""


def access_violation(self, *args, **kwargs):
    method_name = kwargs.pop('method_name')
    self._access_violation(method_name, *args, **kwargs)


def create_restricted_object_cls(dont_override_methods=[]):
    dont_override_methods = set(dont_override_methods)

    class RestrictedObject(object):
        def _access_violation(self, method_name, *args, **kwargs):
            raise TypeError(method_name, args, kwargs)

    for method in methods.split('\n'):
        method = method.strip()
        if not method or method.startswith('#'):
            continue
        if method in dont_override_methods:
            dont_override_methods.remove(method)
            continue

        # XXX: functools.partial objects have no __get__
        def method_access_violation(self, method_name=method, *args, **kwargs):
            self._access_violation(method_name, *args, **kwargs)

        setattr(RestrictedObject, method, method_access_violation)
    if dont_override_methods:
        raise ValueError("Unknown attributes", dont_override_methods)
    return RestrictedObject
