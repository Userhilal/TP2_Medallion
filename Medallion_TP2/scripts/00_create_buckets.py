from minio import Minio

client = Minio(
    "localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False,
)

for bucket in ["bronze", "silver", "gold"]:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        print(f"Bucket {bucket} créé")
    else:
        print(f"Bucket {bucket} existe déjà")
