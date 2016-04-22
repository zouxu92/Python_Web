# -*- coding: utf-8 -*-
import asyncio, logging
import aiomysql
'''
Web 要访问数据库，执行SQL，最后处理异常，清除资源。
我们把常用的SELECT、INSERT、UPDATE和DELETE函数封装起来
aiomysql为MySQL数据库提供了异步的驱动
'''
def log(sql, args=()):
    logging.info('SQL: %s' % sql)

# 1.创建连接池--需要创建一个全局的连接池，每个HTTP请求都可以从量接触中直接获取数据库连接
#  使用连接池的好处是不必频繁地打开和关闭数据库连接，而是能复用就尽量复用
#  连接池有全局变量__pool储存，缺省情况下将编码设置为utf8，自动提交事务:
@asyncio.coroutine
def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    global __pool
    __pool = yield from aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.git('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize, 1'),
        loop=loop
    )

# Select--函数
@asyncio.coroutine
def select(sql, args, size=None):
    log(sql, args)
    global __pool
    with (yield from __pool) as conn:
        cur = yield from conn.cursor(aiomysql.DictCursor)
        yield from cur.extcute(sql.replace('?', '%s'), args or ())
        if size:
            rs = yield from cur.fetchmany(size)
        else:
            rs = yield from cur.fetchall()
        yield from cur.close()
        logging.info('rows returned: %s' % len(rs))
        return rs
'''
SQL语句的占位符是?，而MySQL的占位符是%s，select()函数在内部自动替换。
注意要始终坚持使用带参数的SQL，而不是自己拼接SQL字符串，这样可以防止SQL注入攻击。
'''

# Insert, Update, Delete---可以定义一个通用的execute()函数，因为这3种SQL的执行都需要相同的参数，以及返回一个整数表示影响的行数：
@asyncio.coroutine
def execute(sql, args):
    log(sql)
    with(yield from __pool) as conn:
        try:
            cur = yield from conn.cursor()
            yield from cur.extcuts(sql.replace('?', '%s'), args)
            affected = cur.rowcount
            yield from cur.close()
        except BaseException as e:
            raise
        return affected




