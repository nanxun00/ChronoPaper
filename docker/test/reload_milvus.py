from pymilvus import connections, CollectionSchema, FieldSchema, Collection, utility, DataType

# 连接到 Milvus 服务器
# 默认情况下，Milvus 运行在本地的 19530 端口
connections.connect("default", host="47.103.8.209", port="19024")

# 获取所有集合的名称
collections = utility.list_collections()
print(collections)

# # 遍历所有集合并删除
# for collection_name in collections:
#     try:
#         # 删除集合
#         utility.drop_collection(collection_name)
#         print(f"Collection {collection_name} deleted successfully.")
#     except Exception as e:
#         # 如果集合不存在或其他错误，打印错误信息
#         print(f"Failed to delete collection {collection_name}: {e}")
#
# # 再次确认所有集合是否已被删除
# remaining_collections = utility.list_collections()
# if not remaining_collections:
#     print("All collections have been deleted.")
# else:
#     print(f"Remaining collections: {remaining_collections}")


# 定义集合结构
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=128),  # 假设我们有一个128维的向量字段
    FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=255)  # 指定 VARCHAR 字段的最大长度
]

schema = CollectionSchema(fields, description="A collection with vector and scalar fields")

# 创建集合
collection_name = "k523af537"
try:
    collection = Collection(name=collection_name, schema=schema)
    print(f"集合 {collection_name} 创建成功")
except Exception as e:
    print(f"创建集合 {collection_name} 失败: {e}")