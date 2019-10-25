from datetime import datetime

from django.shortcuts import render
from django_redis import get_redis_connection
from rest_framework import status, mixins
from rest_framework.decorators import action
from rest_framework.generics import CreateAPIView, RetrieveAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework_jwt.utils import jwt_response_payload_handler
from rest_framework_jwt.views import ObtainJSONWebToken

from carts.utils import merge_cookie_cart_to_redis
from goods.models import SKU
from goods.serializers import SKUSerializer
from users import constants
from users.models import User
from users.serializers import CreateUserSerializer, UserDetailSerializer, EmailSerializer, UserAddressSerializer, \
    AddressTitleSerializer, AddUserBrowsingHistorySerializer


class UsernameCountView(APIView):
    """
    用户名数量
     获取用户名的数量:
        1. 根据username查询用户的数量
        2. 返回应答
    """
    def get(self, request, username):
        """
        获取指定用户名数量
        """
        count = User.objects.filter(username=username).count()

        data = {
            'username': username,
            'count': count
        }
        return Response(data)


class MobileCountView(APIView):
    """
    手机号数量
    """
    def get(self, request, mobile):
        """
        获取指定手机号数量
        """
        count = User.objects.filter(mobile=mobile).count()

        data = {
            'mobile': mobile,
            'count': count
        }
        return Response(data)


# POST /users/
class UserView(CreateAPIView):
    """
    用户注册
    """
    serializer_class = CreateUserSerializer

    # def post(self, request):
    #     """
    #     注册用户信息的保存(用户创建):
    #     1. 获取参数并进行校验(参数完整性，手机号格式，手机号是否注册，是否同意协议，两次密码是否一致，短信验证码是否正确）
    #     2. 创建新用户并保存注册用户的信息
    #     3. 将新用户数据序列化返回
    #     """
    #     # 1. 获取参数并进行校验(参数完整性，手机号格式，手机号是否注册，是否同意协议，两次密码是否一致，短信验证码是否正确）
    #     serializer = self.get_serializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #
    #     # 2. 创建新用户并保存注册用户的信息(create)
    #     serializer.save()
    #
    #     # 3. 将新用户数据序列化返回
    #     return Response(serializer.data, status=status.HTTP_201_CREATED)


# GET /user/
class UserDetailView(RetrieveAPIView):
    """
    用户详情
    """
    serializer_class = UserDetailSerializer
    # 指定当前视图的权限控制类，此处是仅认证的用户才能进行访问
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # 返回当前登录的用户对象
        # self.request: request请求对象
        return self.request.user

    # def get(self, request):
    #     """
    #     self.request: request请求对象
    #     request.user:
    #         1. 如果用户已认证，request.user就是登录的用户的对象
    #         2. 如果用户未认证，request.user是一个匿名用户类的对象
    #     获取登录用户个人信息:
    #     1. 获取登录用户对象
    #     2. 将登录用户对象序列化并返回
    #     """
    #     # 1. 获取登录用户对象
    #     user = self.get_object() # user = request.user
    #
    #     # 2. 将登录用户对象序列化并返回
    #     serializer = self.get_serializer(user)
    #     return Response(serializer.data)


class EmailView(UpdateAPIView):
    """
    保存用户邮箱
    """
    # 登录用户权限设置
    permission_classes = [IsAuthenticated]
    serializer_class = EmailSerializer

    def get_object(self, *args, **kwargs):
        return self.request.user


class VerifyEmailView(APIView):
    """
    邮箱验证
     用户邮箱验证:
        1. 获取token参数并进行校验(token必传，对token解密)
        2. 将对应的用户邮箱验证标记email_active设置为True
        3. 返回应答
    """
    def put(self, request):
        # 获取token
        token = request.query_params.get('token')
        if not token:
            return Response({'message': '缺少token'}, status=status.HTTP_400_BAD_REQUEST)

        # 验证token
        user = User.check_verify_email_token(token)
        if user is None:
            return Response({'message': '链接信息无效'}, status=status.HTTP_400_BAD_REQUEST)

        # 设置用户的邮箱验证标记
        user.email_active = True
        user.save()
        return Response({'message': 'OK'})


class AddressViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, GenericViewSet):
    """
    用户地址新增与修改
    """
    serializer_class = UserAddressSerializer
    permissions = [IsAuthenticated]

    def get_queryset(self):
        # 返回视图使用的查询集
        return self.request.user.addresses.filter(is_deleted=False)

    # GET /addresses/
    def list(self, request, *args, **kwargs):
        """
        获取用户的收货地址数据:
        1. 查询用户的收货地址数据
        2. 将用户的收货地址数据序列化并返回
        """
        # 1. 查询用户的收货地址数据
        # addresses = request.user.addresses.filter(is_deleted=False)
        queryset = self.get_queryset()

        # 2.序列化
        serializer = self.get_serializer(queryset, many=True)
        user = self.request.user
        return Response({
            'user_id': user.id,
            'default_address_id': user.default_address_id,
            'limit': constants.USER_ADDRESS_COUNTS_LIMIT,
            'addresses': serializer.data,
        })

    # POST /addresses/
    def create(self, request, *args, **kwargs):
        """
        保存用户地址数据
        request.user: 获取登录用户
        新增地址数据的保存:
        0. 地址数量上限判断(用户的地址是否超过最大地址数量)
        1. 获取参数并进行校验(参数完整性，手机号格式，邮箱格式)
        2. 创建并保存新增地址的数据
        3. 将新增地址数据序列化并返回
        """
        # 检查用户地址数据数目不能超过上限
        count = request.user.addresses.filter(is_deleted=False).count()
        if count >= constants.USER_ADDRESS_COUNTS_LIMIT:
            return Response({'message': '保存地址数据已达到上限'}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)

    # delete /addresses/<pk>/
    def destroy(self, request, *args, **kwargs):
        """
        处理删除
        """
        address = self.get_object()

        # 进行逻辑删除
        address.is_deleted = True
        address.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    # put /addresses/pk/status/
    @action(methods=['put'], detail=True)
    def status(self, request, pk=None):
        """
        设置默认地址
        """
        address = self.get_object()
        request.user.default_address = address
        request.user.save()
        return Response({'message': 'OK'}, status=status.HTTP_200_OK)

    # put /addresses/pk/title/
    # 需要请求体参数 title
    @action(methods=['put'], detail=True)
    def title(self, request, pk=None):
        """
        修改标题
        """
        address = self.get_object()
        serializer = AddressTitleSerializer(instance=address, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserBrowsingHistoryView(CreateAPIView):
    """
    用户浏览历史记录
    """
    serializer_class = AddUserBrowsingHistorySerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        获取
        """
        user_id = request.user.id

        redis_conn = get_redis_connection("history")
        history = redis_conn.lrange("history_%s" % user_id, 0, constants.USER_BROWSING_HISTORY_COUNTS_LIMIT - 1)
        skus = []
        # 为了保持查询出的顺序与用户的浏览历史保存顺序一致
        for sku_id in history:
            sku = SKU.objects.get(id=sku_id)
            skus.append(sku)

        serializer = SKUSerializer(skus, many=True)
        return Response(serializer.data)


# POST /authorizations/
class UserAuthorizeView(ObtainJSONWebToken):
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # 账户名和密码正确
            user = serializer.object.get('user') or request.user
            token = serializer.object.get('token')
            response_data = jwt_response_payload_handler(token, user, request)
            response = Response(response_data)
            if api_settings.JWT_AUTH_COOKIE:
                expiration = (datetime.utcnow() +api_settings.JWT_EXPIRATION_DELTA)
                response.set_cookie(api_settings.JWT_AUTH_COOKIE,
                                    token,
                                    expires=expiration,
                                    httponly=True)
            # 调用合并购物车记录的函数
            merge_cookie_cart_to_redis(request, user, response)
            return response

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

