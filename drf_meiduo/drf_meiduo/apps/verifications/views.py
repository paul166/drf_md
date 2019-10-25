import random

from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.response import Response

from drf_meiduo.settings.dev import APIKEY
from drf_meiduo.utils.yunpian import YunPian
from verifications import constants

from rest_framework.views import APIView

# 获取日志器
import logging
logger = logging.getLogger('django')
# Create your views here.


# GET /sms_codes/(?P<mobile>1[3-9]\d{9})/
class SMSCodeView(APIView):
    '''发送短信验证码'''

    def get(self, request, mobile):
        """
        短信验证码获取：
        1. 随机生成6位数字作为短信验证码内容
        2. 在redis中存储短信验证码的内容，以`sms_<mobile>`作为key，以短信验证码内容为value
        3. 使用云通讯给`mobile`发送短信验证码
        4. 返回应答，发送成功
        """
        # 获取redis链接对象
        redis_conn = get_redis_connection('verify_codes')

        # 判断send_flag_<mobile>在redis是否存在
        send_flag = redis_conn.get('send_flag_%s' % mobile) # None

        if send_flag:
            # 60s之内
            return Response({'message': '发送短信过于频繁'}, status=status.HTTP_403_FORBIDDEN)

        # 1. 随机生成6位数字作为短信验证码内容
        sms_code = '%06d' % random.randint(0, 999999) # 000010
        print(sms_code)

        logger.info('短信验证码为: %s' % sms_code)

        # 2. 在redis中存储短信验证码的内容，以`sms_<mobile>`作为key，以短信验证码内容为value
        # 创建redis管道对象
        pl = redis_conn.pipeline()

        # 向redis中添加指令
        # redis_conn.set('<key>', '<value>', '<expires>')
        pl.set('sms_%s' % mobile, sms_code, constants.SMS_CODE_REDIS_EXPIRES)
        # 存储一个发送短信标记 key: send_flag_<mobile> expires: 60s
        pl.set('send_flag_%s' % mobile, 1, constants.SEND_SMS_INTERVAL)

        # 一次执行管道中所有命令
        pl.execute()

        # 3. 使用云通讯给`mobile`发送短信验证码
        expires = constants.SMS_CODE_REDIS_EXPIRES // 60

        # 发出发送短信任务消息(通知worker来调用发送短信任务函数)
        # send_sms_code.delay(mobile, sms_code, expires)
        try:
            # ccp = CCP()
            # # 调用云通信发送短信验证码
            # res = ccp.send_template_sms(mobile, [code, expires], SMS_CODE_TEMP_ID)
            yunpian = YunPian(APIKEY)
            sms_status = yunpian.send_sms(code=sms_code, mobile=mobile)
        except Exception as e:
            return Response({"message": "发送短信异常"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if sms_status['code'] != 0:
            return Response({"message": "发送短信失败"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # 4. 返回应答，发送成功
        return Response({'message': 'OK'},status=status.HTTP_201_CREATED)
