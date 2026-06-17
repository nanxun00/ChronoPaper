# from utils import logger

if __name__ == "__main__":
    from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection

    connections.connect("default", host="47.103.8.209", port="19024")

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=128)
    ]

    schema = CollectionSchema(fields)

    collection_name = "test_collection"
    try:
        collection = Collection(name=collection_name, schema=schema)
        print("已连接")
    except Exception as e:
        print(f"Failed to create or connect to the collection {collection_name}: {str(e)}")
    else:
        print(f"Successfully connected to the collection {collection_name}")