# -*— coding:utf-8 -*-


import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web

from .apis import APIError

# get 和 post 为修饰方法,主要是为对象加上'__method__' 和'__route__'属性
# 为了把我们定义的url实际处理方法,以get请求或post请求的区分
def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

def post(path):
    '''
    Define decorator @post('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator
# 关于inspect.Parameter 的 kind 类型有5种:
# POSITIONAL_ONLY           只能是位置参数
# POSITIONAL_OR_KEYWORD     可以是位置参数也可以是关键字参数
# VAR_POSITIONAL            相当于是 *args
# KEYWORD_ONLY              关键字参数提供了key, 相当于是 *, key
# VAR_KEYWORD               相当于是 **kw


# 如果url处理函数需要传入关键字,且默认是空的话,获取这个key
def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
        return tuple(args)

# 如果url处理函数需要传入关键字参数,回去这个key
def get_name_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args) # 元组

# 如果url处理还是需要传入关键字参数,返回True
def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

# 如果url处理函数的参数是**kw,返回True
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

# 如果url处理函数的参数是request,返True
def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in funtion: %s%s' %(fn.__name__, str(sig)))
    return round

# RequestHandler目的就是从URL函数中分析其需要接受的参数,从request中回去必要的参数调用URL函数
class RequestHandler(object):

    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        # 下面的一系列是为了检测url处理函数的参数类型
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_name_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

        async def __call__(self, request):
            kw = None
            # 如果处理函数需要传入特定key的参数或可变参数的话
            if self._has_var_kw_arg or self._has_var_kw_arg or self._required_kw_args:
                # 如果是post请求,则读请求的body
                if request.method == "POST":
                    # 如果request的头中没有content-type,则返回错误
                    if not request.content_type:
                        return web.HTTPBadRequest('Missing Content-Type.')
                    # 字符串全部转换为小写
                    ct = request.content_type.lower()
                    # 如果是'application/json'类型
                    if ct.startswith('application/json'):
                        # 把request的body,按json的方式输出一个字典
                        params = await request.json()
                        # 解读出错或params不是一个字典,则返回错误描述
                        if not isinstance(params, dict):
                            return web.HTTPBadRequest('JSON body must be object.')
                        # 保存这个params
                        kw = params
                    # 如果是'application/x-www-form-rulencoded',或 'multipart/form-data'，直接读出来并保存
                    elif ct.startswith('application/x-www-form-urlencoden') or ct.startswith('multipart/form-data'):
                        params = await request.post()
                        kw = dict(**params)
                    else:
                        return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
                # 如果是get请求,则读请求url字符串
                if request.method == "GET":
                    # 看url有没有参数,即? 后面的字符串
                    qs = request.query_string
                    if qs:
                        # 如果有的话,则把产生以键值的放肆存起来赋值个kw
                        kw = dict()
                        for k, v in parse.parse_qs(qs, True).items():
                            kw[k] = v[0]
            # 如果kw为空的话,kw设置为request.mathch_info
            if kw is None:
                kw = dict(**request.match_info)
            else:
                # 如果kw有值的话
                # 如果处理方式需要传入 **kw,且需要传入关键字参数
                if not self._has_var_kw_arg and self._named_kw_args:
                    # remove all unamed kw:
                    copy = dict()
                    # 从kw中筛选出url处理方法需要传入的参数对
                    for name in self._named_kw_args:
                        if name in kw:
                            copy[name] = kw[name]
                    kw = copy
                # check named arg:
                # 从match_info中筛选出url处理方法需要传入的参数对
                for k, v in request.match_info.items():
                    if k in kw:
                        logging.warning("Duplictae arg name in anmed arg and kw args:%s" % k)
                    kw[k] = v
            # 如果参数需要传'request'参数,则把request实例出传入
            if self._has_request_arg:
                kw['request'] = request

            # 如果参数有默认为None的关键子参数,遍历一下kw,如果kw中没有这个key,抛错
            if self._required_kw_args:
                for name in self._required_kw_args:
                    if not name in kw:
                        return web.HTTPBadRequest('Missing argument: %s' % name)
            logging.info('call with args: %s' % str(kw))
            try:
                # 对url进行处理
                r = await self._func(**kw)
                return r
            except APIError as e:
                return dict(error=e.error, data=e.data, message=e.message)

# 添加静态页面的路径
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s ==> %s' % ('/static', path))

def add_route(app, fn):
    # 获取'__method__'和'__route__'属性,如果有空则抛出异常
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    # 判断fn是不是协程 并且 判断是不是fn, 是不是一个生成器(generator function)
    if not asyncio.iscoroutinefunction(fn) and not inspect.iscoroutinefunction(fn):
        # 都不是的话,强行修饰为协程
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s ==> %s(%s)'% (method, path, fn.__name__, ','.join(inspect.signature(fn).parameters.keys())))
    # 正式注册为相应的url处理方法
    # 处理方法为RequestHandler的自省函数'__call__'
    app.router.add_route(method, path, RequestHandler(app, fn))

# 自动搜索传入的module_name的module的处理函数
def add_routes(app, module_name):
    # 检查传入的modele_name是否有'.'
    n = module_name.rfind('.')
    # 没有'.',则传入的是module名
    # __import__(module)其实就是 import module
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
    else:

        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    # 遍历mod的方法和属性,主要是找处理方法
    # 由于我们定义的处理方法,被@get或@post修饰过,所以方法里会有'__method__'和'__route__'属性
    for attr in dir(mod):
        # 如果是以'_'开头的,一律pass,我们定义的处理方法不是以'_'开头的
        if attr.startswith('_'):
            continue
        # 获取到非'_'开头的属性和方法
        fn = getattr(mod, attr)
        # 取能调用的,说明是方法
        if callable(fn):
            # 检测'__method__' 和 '__route__'属性
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                # 如果都有,说明是我们定义的处理方法,加到app对象里route中
                add_route(app, fn)



