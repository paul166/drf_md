from django.shortcuts import render
from drf_haystack.viewsets import HaystackViewSet
from rest_framework.filters import OrderingFilter
from rest_framework.generics import ListAPIView

from goods.models import SKU
from goods.serializers import SKUSerializer, SKUIndexSerializer


# GET /categories/(?P<category_id>\d+)/skus/
class SKUListView(ListAPIView):
    """
    sku列表数据
    """
    # 指定视图所使用的序列化器类
    serializer_class = SKUSerializer
    # 指定视图所使用的查询集
    # queryset = SKU.objects.filter(category_id=category_id, is_launched=True)

    # 设置排序
    filter_backends = [OrderingFilter]
    # 设置排序字段
    ordering_fields = ('update_time', 'price', 'sales')

    def get_queryset(self):
        """返回视图所使用的查询集"""
        category_id = self.kwargs['category_id']
        return SKU.objects.filter(category_id=category_id, is_launched=True)


class SKUSearchViewSet(HaystackViewSet):
    """
    SKU搜索
    """
    # 指定索引对应的模型类
    index_models = [SKU]

    # 指定搜索结果所采用的序列化器类
    serializer_class = SKUIndexSerializer
