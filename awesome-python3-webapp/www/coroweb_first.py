# -*- coding:utf-8 -*-

# 时间:2016年04月30日14:49:24
# 在正式开始Web开发前,需要编写一个Web框架
# aiohttp想对比较底层,需要编写一个URL的处理函数,需要自己封装一个

'''
# 第一步,编写一个用@asyncio.coroutine装饰的函数:
@asyncio.coroutine
def headle_url_xxx(request):
    pass

# 第二步,传入的产生需要自己从request中获取:
url_param = request.match_info['key']
query_params = parse_qs(request.query_string)

# 最后,需要自己构造Resqonse对象
text = rander('template', data)
return web.Response(text.encode('utf-8'))
'''

# Web框架的设计师完全从使用者出发,目的是上使用者编写尽可能少的代码
# 编写简单的函数而非引入request和web.Response还有一个好处,可以单独测试,否则需模拟一个request

# @get 和 @post

# 要不一个函数映射为一个URL处理函数,我们先定义@get()

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
    pass


# 定义RequestHandle
# URL处理函数不一定是一个coroutine(协程),因此我们用RequestHandler()来封装处理函数.
'''
RequestHandler是一个类,定义__call__()方法,可以将其实例视为函数.
RequestHandler 目的就是从URL函数中分析其需要接收的参数,从request中获取必要的产生,
调用URL函数,然后把结果转换为web.Response对象,这样就完全符合aiohttp框架的需求:
'''

class RequestHandler(object):
    def __init__(self, app, fn):
        self._app = app
        self._func = fn


    @asyncio.coroutine
    def __call__(self, request):
        kw = 1 # ... 回去参数
        r = yield from self._func(**kw)
        return r

# 编写一个add_route 函数,用来注册一个URL处理函数:
def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defied in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s ==> %s(%s)' % (method, path, fn.__name__, ','.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))
'''
# 最后一步,把很多次add_route()注册的调用:
add_route(app, handles.index)
add_route(app, handles.blog)
add_route(app, handles.create_comment)
...
变成自动扫描
# 自动把handler模块的所有付款条件的函数注册了:
add_routes(app, 'handles')
'''
# add_routes() 定义:
def add_routes(app, modele_name):
    n = modele_name.rfind('.')
    if n == (-1):
        mod = __import__(modele_name, globals(), locals())
    else:
        name = modele_name[n+1:]
        mod = getattr(__import__(modele_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)

'''
最后,在app.py中加入middleware , jinja2模板和自注册支持:
app = web.Application(loop=loop, middlewares=[
    logger_factory, response_factory
])
init_jinja2(app, filters=dict(detetime=datetime_filter))
add_route(app, 'handlers')
add_static(app)
'''

#  =============分割线==============
'''
middleware 是一种拦截器,一个URL在被某个函数处理前,可经过一系列的middleware的处理
一个middleware可以改变URL的输入,输出,升值可以决定不继续处理而直接返回.
'''
# middleware的用处就是在于把通用的功能从每个URL处理函数中拿出来,集中放到一个地方.
# 例如,一个记录URL日志的logger可以简单定义如下:
@asyncio.coroutine
def logger_factory(app, handler):
    @asyncio.coroutine
    def logger(request):
        # 记录日志:
        logging.info('Request: %s %s' % (request.method, request.path))
        # 继续处理请求:
        return (yield from handler(request))
    return logger

# 而response这个middleware把返回值转换为web.Response对象再返回,以保证满足aiohttp的要求:
@asyncio.coroutine
def response_factory(app, handler):
    @asyncio.coroutine
    def response(requset):
        # 结果:
        r = yield from handler(requset)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'applicotion/octet-stream'
            return resp
        if isinstance(r, str):
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r, dict):
            pass


































