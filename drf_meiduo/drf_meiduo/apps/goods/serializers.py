from goods.models import SKU
from rest_framework import serializers
from drf_haystack.serializers import HaystackSerializer
from goods.search_indexes import SKUIndex


class SKUSerializer(serializers.ModelSerializer):

    class Meta:
        model = SKU
        fields = ('id', 'name', 'price', 'default_image_url', 'comments')


class SKUIndexSerializer(HaystackSerializer):
    """
    搜索结果数据序列化器
    """
    object = SKUSerializer(label='商品')

    class Meta:
        index_classes = [SKUIndex]
        fields = ('text', 'object')