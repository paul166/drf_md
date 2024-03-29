from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django_redis import get_redis_connection
from rest_framework import serializers
from goods.models import SKU
from orders.models import OrderInfo, OrderGoods


class OrderSKUSerializer(serializers.ModelSerializer):
    """
    购物车商品数据序列化器
    """
    count = serializers.IntegerField(label='数量')

    class Meta:
        model = SKU
        fields = ('id', 'name', 'default_image_url', 'price', 'count')


class SaveOrderSerializer(serializers.ModelSerializer):
    """订单创建的序列化器类"""

    class Meta:
        model = OrderInfo
        fields = ('order_id', 'address', 'pay_method')

        extra_kwargs = {
            'order_id': {
                'read_only': True
            },
            'address': {
                'write_only': True
            },
            'pay_method': {
                'write_only': True,
                'required': True
            }
        }

    def create(self, validated_data):
        """创建并保存订单的信息"""
        # 获取address和pay_method
        address = validated_data['address']
        pay_method = validated_data['pay_method']

        # 组织参数
        # 获取登录user
        user = self.context['request'].user

        # 订单id: 年月日时分秒+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + '%010d' % user.id

        # 订单商品总数据和实付款
        total_count = 0
        total_amount = Decimal(0)

        # 运费: 10
        freight = Decimal(10)

        # 订单状态
        status = OrderInfo.ORDER_STATUS_ENUM['UNSEND'] if pay_method == OrderInfo.PAY_METHODS_ENUM['CASH'] else OrderInfo.ORDER_STATUS_ENUM['UNPAID']

        # 获取redis链接
        redis_conn = get_redis_connection('cart')

        # 从redis set中获取用户所要购买(勾选)的商品id
        cart_selected_key = 'cart_selected_%s' % user.id

        # (b'<sku_id>', b'<sku_id>', ...)
        sku_ids = redis_conn.smembers(cart_selected_key)

        # 从redis hash中获取用户购物车中商品的id和对应数量
        cart_key = 'cart_%s' % user.id
        # {
        #     b'<sku_id>': b'<count>',
        #     ...
        # }
        cart_dict = redis_conn.hgetall(cart_key)

        with transaction.atomic():
            # with语句块下面的代码，凡是涉及到数据库操作的代码，在进行数据库操作时，都会放在同一个事务中

            # 订单并解决方案——乐观锁 --->>>事务
            # 设置事务保存点
            sid = transaction.savepoint()

            try:
                # 1）向订单基本信息表添加一条记录
                order = OrderInfo.objects.create(
                    order_id=order_id,
                    user=user,
                    address=address,
                    total_count=total_count,
                    total_amount=total_amount,
                    freight=freight,
                    pay_method=pay_method,
                    status=status
                )

                # 2）订单中包含几个商品，就需要向订单商品表添加几条记录
                for sku_id in sku_ids:
                    # 获取该商品购买的数量
                    count = cart_dict[sku_id]
                    count = int(count)

                    # 根据sku_id获取对应的商品
                    sku = SKU.objects.get(id=sku_id)

                    # 判断商品的库存是否足够
                    if count > sku.stock:
                        # 回滚事务到sid保存点
                        transaction.savepoint_rollback(sid)
                        raise serializers.ValidationError('商品库存不足')

                    # 减少商品的库存，增加销量
                    sku.stock -= count
                    sku.sales += count
                    sku.save()

                    # 向订单商品表中添加一条记录
                    OrderGoods.objects.create(
                        order=order,
                        sku=sku,
                        count=count,
                        price=sku.price
                    )

                    # 累加计算订单商品的总数量和总金额
                    total_count += count
                    total_amount += sku.price*count

                # 实付款
                total_amount += freight
                # 更新order中商品的总数量和实付款
                order.total_count = total_count
                order.total_amount = total_amount
                order.save()
            except serializers.ValidationError:
                # 继续向外抛出捕获的异常
                raise
            except Exception as e:
                # 回滚事务到sid保存点
                transaction.savepoint_rollback(sid)
                raise serializers.ValidationError('下单失败1')

        # 3）清除redis中已下单的对应购物车记录
        pl = redis_conn.pipeline()
        pl.hdel(cart_key, *sku_ids)
        pl.srem(cart_selected_key, *sku_ids)
        pl.execute()

        # 返回订单
        return order