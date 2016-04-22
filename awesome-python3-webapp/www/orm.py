# -*- coding: utf-8 -*-
'''
时间:2016年04月22日22:25:57
有了select()和execute()函数就可以编写一个简单的ORM了.
解释:对象关系映射（英语：Object Relational Mapping，简称ORM，
或O/RM，或O/R mapping），是一种程序技术，用于实现面向对象编程语言里
不同类型系统的数据之间的转换

'''

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







# 先考虑如何定义一个User对象,然后把数据库表users和它关联起来.

from orm import Model, StringField, IntegerField

class User(Model):
    __table__ = 'users'

    id = IntegerField(primary_key=True)
    name = StringField()

    # Model类中添加class方法,让所有子类调用class方法:
    @classmethod
    @asyncio.coroutine
    def find(cls, pk):
        ' find object by primary key.'
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0 :
            return None
        return cls(**rs[0])

    # Model类中添加实例方法,让所有子类调用实例方法:
    @asyncio.coroutine
    def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = yield from execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)




# 注意:定义在User类中的__table__ , id 和 name 是类的属性,不是实例的属性.
# so,在类级别定义的属性来描述User对象和映射关系,而实例属性必须通过__init__()方法初始化,两者不干扰:

# 创建实例:
user = User(id=123, name='Micha')
# 存入数据库:
user.instert()
# 查询所有User对象:
users = User.findAll()

# 定义Model-->首先要定义的是所有ORM映射的基类Model:
class Model(dict, metaclass=ModelMetaclass):

    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribut  '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using dafault value for %s:%s' % (key, str(value)))
                setattr(self, key, value)
            return value

# Field和Field子类:
class field(object):

    def __init__(self, name, colume_type, primary_key, default):
        self.name = name
        self.colume_type = colume_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.colume_type, self.name)

# 映射varchar的StringField:
class StringField(Field):

    def __init__(self, name=None, primary_key=False, default=None, dd1='varchar(100)'):
        super().__init__(name, dd1, primary_key, default)

# Model只是基类,通过metaclass: ModelMetaclass, 映射信息读取出来:
class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        # 排除Model类本身:
        if name=="Model":
            return type.__new__(cls, name, bases, attrs)
        # 获取table名称:
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s' % (name, tableName))
        # 获取所有的Field和主键名:
        mappings = dict()
        fields = []
        primaryKey = None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info(' found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                if v.primarykey:
                    # 找到主键:
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)
            if not primaryKey:
                raise RuntimeError('Primary key not found.')
            for k in mappings.keys():
                attrs.pop(k)
            escaped_fields = list(map(lamdba f: '`%s`' % f, fields))
            attrs['__mappings__'] = mappings # 保存属性和列的映射关系
            attrs['__table__'] = tableName
            attrs['__primary_key__'] = primaryKey # 主键属性名
            attrs['__fields__'] = fields # 除主键外的属性名
            # 构造默认的SELECT, INSTERT, UPDATE和DELETE语句:
            attrs['__select__'] = 'select "%s", %s from "%s"' % (primaryKey, ','.join(escaped_fields), tableName)
            attrs['__insert__'] = "insert into '%s' (%s, '%s') values (%s)" % (tableName, ','.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
            attrs['__update__'] = "update '%s' set %s where '%s'=?" % (tableName, ','.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
            attrs['__delete__'] = "delete from `%s` where `%s`=?" % (tableName, primaryKey)
            return type.__new__(cls, name, bases, attrs)




