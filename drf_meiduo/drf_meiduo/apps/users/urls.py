from django.conf.urls import url
from rest_framework.routers import DefaultRouter
from rest_framework_jwt.views import obtain_jwt_token

from . import views

urlpatterns = [

    url(r'^usernames/(?P<username>\w{5,20})/count/$', views.UsernameCountView.as_view()),
    url(r'^mobiles/(?P<mobile>1[3-9]\d{9})/count/$', views.MobileCountView.as_view()),

    # 注册post
    url(r'^users/$', views.UserView.as_view()),

    # drf JWT提供了登录签发JWT的视图
    url(r'^authorizations/$', obtain_jwt_token),

    # 个人中心
    url(r'^user/$', views.UserDetailView.as_view()),
    url(r'^email/$', views.EmailView.as_view()),  # 设置邮箱
    url(r'^emails/verification/$', views.VerifyEmailView.as_view()),

    # 浏览商品的历史
    url(r'^browse_histories/$', views.UserBrowsingHistoryView.as_view()),

    # 购物车合并 普通登录
    url(r'^authorizations/$', views.UserAuthorizeView.as_view()),



]

router = DefaultRouter()
router.register('addresses', views.AddressViewSet, base_name='addresses')

urlpatterns += router.urls