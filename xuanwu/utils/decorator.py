# -*- coding: utf-8 -*-
"""
  @ Author:   Mr.Hat
  @ Email:    shenghong6560@gmail.com
  @ Date:     2020/9/27 17:17
  @ Description:
  @ History:
"""
import time
import asyncio
import functools

# Coroutine lockers. e.g. {"locker_name": locker}
METHOD_LOCKERS = {}


def async_method_locker(name, wait=True, timeout=1):
    """ 为了在任何异步协程方法之间共享内存，我们应该使用locker来锁定我们的方法，从而避免一些不可预测的操作。

    Args:
        name: 协程锁名称.
        wait: 协程被锁时是否等待执行? True, 等待直到被执行, 否则立即返回（不执行）
        timeout: 锁定超时时间，默认为1s。

    NOTE:
        此修饰符只能用于`async`方法.
    """
    assert isinstance(name, str)

    def decorating_function(method):
        global METHOD_LOCKERS
        locker = METHOD_LOCKERS.get(name)
        if not locker:
            locker = asyncio.Lock()
            METHOD_LOCKERS[name] = locker

        @functools.wraps(method)
        async def wrapper(*args, **kwargs):
            if not wait and locker.locked():
                return
            try:
                await locker.acquire()
                return await asyncio.wait_for(method(*args, **kwargs), timeout)
            finally:
                locker.release()

        return wrapper

    return decorating_function


"""
在函数执行出现异常时自动重试的简单装饰器
"""


class StopRetry(Exception):

    def __repr__(self):
        return 'retry stop'


def retry(max_retries: int = 5, delay: (float) = 0, step: (float) = 0,
          exceptions: (BaseException, tuple, list) = BaseException,
          sleep=time.sleep, callback=None, validate=None):
    """
    函数执行出现异常时自动重试的简单装饰器。
    :param max_retries:  最多重试次数。
    :param delay:  每次重试的延迟，单位秒。
    :param step:  每次重试后延迟递增，单位秒。
    :param exceptions:  触发重试的异常类型，单个异常直接传入异常类型，多个异常以tuple或list传入。
    :param sleep:  实现延迟的方法，默认为time.sleep。
    在一些异步框架，如tornado中，使用time.sleep会导致阻塞，可以传入自定义的方法来实现延迟。
    自定义方法函数签名应与time.sleep相同，接收一个参数，为延迟执行的时间。
    :param callback: 回调函数，函数签名应接收一个参数，每次出现异常时，会将异常对象传入。
    可用于记录异常日志，中断重试等。
    如回调函数正常执行，并返回True，则表示告知重试装饰器异常已经处理，重试装饰器终止重试，并且不会抛出任何异常。
    如回调函数正常执行，没有返回值或返回除True以外的结果，则继续重试。
    如回调函数抛出异常，则终止重试，并将回调函数的异常抛出。
    :param validate: 验证函数，用于验证执行结果，并确认是否继续重试。
    函数签名应接收一个参数，每次被装饰的函数完成且未抛出任何异常时，调用验证函数，将执行的结果传入。
    如验证函数正常执行，且返回False，则继续重试，即使被装饰的函数完成且未抛出任何异常。
    如回调函数正常执行，没有返回值或返回除False以外的结果，则终止重试，并将函数执行结果返回。
    如验证函数抛出异常，且异常属于被重试装饰器捕获的类型，则继续重试。
    如验证函数抛出异常，且异常不属于被重试装饰器捕获的类型，则将验证函数的异常抛出。
    :return: 被装饰函数的执行结果。
    """

    def wrapper(func):
        @functools.wraps(func)
        async def _wrapper(*args, **kwargs):
            nonlocal delay, step, max_retries
            func_ex = StopRetry
            while max_retries > 0:
                try:
                    success, error = await func(*args, **kwargs)
                    # 验证函数返回False时，表示告知装饰器验证不通过，继续重试
                    if callable(validate) and validate(error) is False:
                        continue
                    else:
                        return success, error
                except exceptions as ex:
                    func_ex = ex
                    # 回调函数返回True时，表示告知装饰器异常已经处理，终止重试
                    if callable(callback) and callback(ex) is True:
                        return
                finally:
                    max_retries -= 1
                    if delay > 0 or step > 0:
                        sleep(delay)
                        delay += step
            else:
                raise func_ex

        return _wrapper

    return wrapper
