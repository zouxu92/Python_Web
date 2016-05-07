# -*- coding: utf-8 -*-

# 时间:2016年04月24日05:00:00

import asyncio, logging

import aiomysql

def log(sql, args=()):
    logging.info('SQL: %s' % sql)

# 创建全局数据库连接池,使每个http请求都能从连接池中直接获取数据库连接
# 避免频繁地打开或关闭数据库连接
async def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    global __pool # 定义全局变量
    # 调用一个子协程来创建全局连接池,creste_pool的返回值是一个pool实例对像
    __pool = await aiomysql.create_pool(
        # 前面几项为设置连接的属性
        host=kw.get('host', 'localhost'),     # 数据库服务器的位置,
        port=kw.get('port', 3306),            # mysql的端口
        user=kw['user'],                      # 登录用户名
        password=kw['password'],              # 密码
        db=kw['db'],                          # 当前数据库名
        charset=kw.get('charset', 'utf8'),    # 设置连接使用的编码格式为utf-8
        autocommit=kw.get('autocommit', True),# 自动提交模式,默认是False

        # 下面三项是可选项
        maxsize=kw.get('maxsize', 10),  # 最大连接池大小,默认是10
        minsize=kw.get('minsize', 1),   # 最小连接池大小,默认是10
        loop=loop    # 设置消息循环
    )

# Select 操作 sql形参即为sql语句, args表示填入sql的选项值
# size用于指定最大的查询数量,不指定将返回所有查询结果
async def select(sql, args, size=None):  # async协程
    log(sql, args)
    global __pool
    # 从连接池中获取一条数据连接
    async with __pool.get() as conn:
        # 打开一个DictCursor,它与普通游标的不同在于,以dict形式返回结果
        async with conn.cursor(aiomysql.DictCursor) as cur:
        # sql语句的占位符为"?",mysql的占位符为"%s",因此需要进行替换
        # 若没有指定args,将使用默认的select语句(在Meatclass内定义的)进行查询
            await cur.execute(sql.replace('?', '%s'), args or ())
        if size:
            rs = await cur.fetchmany(size)
        else:
            rs = await cur.fetchall()
        logging.info('rows returned: %s' % len(rs))
        return rs

# 增删改的是对数据库的修改,因此封装在一个函数中
async def execute(sql, args, autocommit=True):
    log(sql)
    async with __pool.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            # 此处打开的是一个普通游标
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.extcute(sql.replace('?', '%s'), args)
                affected = cur.rowcount # 增删改,返回影响的行数
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            if not autocommit:
                await conn.rollback()
            raise
        return affected

# 构造占位符
def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ','.join(L)

# 父域,可被其他继承
class Field(object):

    # 域的初始化,包括属性(列)名,属性(列)的类型,是否主键
    # default参数允许orm自己填入省缺值,因此具体的使用请看的具体的类怎么使用
    # 比如User有一个定义在StringField的id,default就用于存储用户的独立id
    # 再比如created_at的default就用于存储创建时间的浮点表示
    def __init__(self, name, colume_type, primary_key, default):
        self.name = name
        self.colume_type = colume_type
        self.primary_key = primary_key
        self.default = default

    # 用于打印信息,依次为类名(域名),属性类型,属性名
    def __str__(self):
        return '<%s, %s:%s> ' % (self.__class__.__name__, self.colume_type, self.name)

class StringField(Field): # string类型处理,调用父类方法初始化

    # ddl("data definition languages"),用于定义数据类型
    # varchar("variable char"), 可变长度的字符串,以下定义中的100表示最长长度,即字符串的可变范围为0~100
    # (char,为不可变长度字符串,会用空格字符补齐)
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)

class BooleanField(Field):

    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)

class IntegerFiled(Field):

    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)

class FloatField(Field):

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', False, default)

class TextField(Field):

    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


# 这是个元类,它定义了如果构造一个类,任何定义了__metaclass__属性或指定metaclass的都会通过元类定义的构造方法构造类
# 任何继承自Model的类,都会自动通过ModelMetaclass扫描映射关系,并存储到自身的类属性
class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        # cls:当前准备创建的类对象,相当于self
        # name:类名,继承自Model.
        # bases:父类的元组
        # attrs:属性(方法)的字典,比如User有__table__,id,等,就作为attrs的keys
        # 排除Model类本身,因为Model累主要就是用来被继承的,其不存在与数据库表的映射
        if name=="Model":
            return type.__new__(cls, name, bases, attrs)

        # 以下是针对"Model"的子类处理,将被用于子类的创建.metaclass将隐式地被继承

        # 获取表名,若没有定义__table__属性,将类名作为表名.此处注意 or 的用法
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table:%s' % (name, tableName))
        # 获取所有的Field和主键名
        mappings = dict()   # 用字典来储存类属性与数据库表的列的映射关系
        fields = []         # 用于保存除主键外的属性
        primaryKey = None   # 用于保存主键

        # 遍历类的属性,找出定义的域,找出定义的域(如StringField,字符串域)内的值,建立映射关系
        # k是属性名,v是起定义域!请看name=StringField(ddl="varchar50")
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info(' found mapping: %s ==> %s' %(k, v))
                mappings[k] = v     # 建立映射关系
                if v.primary_key:   # 找到主键
                    if primaryKey:  # 若主键已经存在,又找到主键,将报错
                        raise RuntimeError('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k) # 将非主键的属性都加入fields列表中
        if not primaryKey: # 没有找到主键也将报错,因为每张表有且仅有一个主键
            raise RuntimeError('Primary key not found.')
        # 从类属性中删除已加入映射字典的键,避免重名
        for k in mappings.keys():
            attrs.pop(k)
        # 将非主键的属性变形,放入escaped_fields中方便增删改查语句的书写
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__mappings__'] = mappings        # 保存属性和列的映射关系
        attrs['__table__'] = tableName          # 保存表名
        attrs['__primary_key__'] = primaryKey   # 主键属性名
        attrs['__fields__'] = fields            # 除主键以为的属性名

        # 构造默认的select,insert,update,delete语句,使用?做占位符
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ','.join(escaped_fields), tableName)
        # 此处利用create_args_string生成若干个?占位
        # 插入数据库时,要指定表名
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' %  (tableName, ','.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        # 通过主键查找到记录并更新
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ','.join(map(lambda f: '`%s=?'%(mappings.get(f).name or f), fields)), primaryKey)
        # 通过主键删除
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)

# ORM映射基类,继承自dict,通过ModelMetaclass元类来构造类
class Model(dict, metaclass=ModelMetaclass):

    # 初始化函数,调用父类(dict)的方法
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    # 增加__getatrr__方法,使获取属性更方便,即可通过"a.b"的形式
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribut  '%s'" % key)

    # 增加__setatrr__方法,是设置属性更方便,可通过"a.b=c"的形式
    def __setattr__(self, key, value):
        self[key] = value

    # 通过键取值,若值不存在,返回None
    def getValue(self, key):
        return getattr(self, key, None)

    # 通过键取值,若值不存在,则返回默认值
    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]  # field是一个定义域!比如FloatField
            # default 这个属性在这里发挥了充分作用
            if field.default is not None:
                # id的StringField.default=next_id,因此调用该函数生成独立id
                # FloatFiled.default=time.time数,因此调用time.time函数返回当前时间
                # 普通属性的StringField默认为None,因此还是返回None
                value = field.default() if callable(field.default) else field.default
                logging.debug('using dafault value for %s:%s' % (key, str(value)))
                # 通过default取到值后再将其作用当前值
                setattr(self, key, value)
            return value

    @classmethod  # 该装饰器将方法定义为类方法
    async def findAll(cls, where=None, args=None, **kw):
        ' find objects by where clause.'
        sql = [cls.__select__]
        # 我们定义的默认的select语句中是通过主键查找的,并不包含where子句
        # 因此若指定有where,需要在select语句中追加关键字
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('roderBy', None)
        # 接受同为where,此处orderBy通过关键字参数传入
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)

        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value:%s' % str(limit))
        rs = await select(' '.join(sql), args) # 没有指定size,因此会fetchall
        return [cls(**r) for r in rs]

    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        ' find number by select and where. '
        sql =['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    async def find(cls, pk):
        ' find object by primary key. '
        # 我们之前已将将数据库的select操作封装在select函数中,以下select的参数依次就是sql, args, size
        rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        # **表示关键字参数; 注意:我们在select函数中,打开的是DictCursor,它会以dict的形式返回结果
        return cls(**rs[0])

    async def save(self):
        # 我们在定义__insert__时,将主键放在末尾,因为属性与值要一一对应,因此通过append的方式将主键加在最后
        args = list(map(self.getValueOrDefault, self.__fields__))#使用getValueOrDefault方法,可以调用time.time这样的函数来获取值
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = await execute(self.__insert__, args)
        if rows != 1: #插入一条记录,结果影响的条数不等于1,肯定出错了
            logging.warn('failed to insert record: affected rows: %s' % rows)

    async def update(self):
        # 像time.time,next_id之类的函数在插入的时候已经调用过了,没有其他需要实时更新的值,因此调用getValue
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_k__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows: %s' % rows)

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]  # 取消主键做为参数
        rows = await execute(self.__delete__, args)   # 调用默认的Delete语句
        if rows != 1:
            logging.warn('failed to remove by primary key: arrrected rows: %s' % rows)
