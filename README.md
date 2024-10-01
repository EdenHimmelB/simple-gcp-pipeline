## Problem

* Dataset ở dạng NDJSON với mỗi dòng là tổng hợp metadata của một batch database dump jobs của [Wikipedia](https://dumps.wikimedia.org/).

```
{"jobs": {"xmlstubsdumprecombine": {"status": "done", "updated": "2024-07-22 09:14:34", "files": {"enwiki-20240720-stub-meta-history.xml.gz": {"size": 104302861395, "url": "/enwiki/20240720/enwiki-20240720-stub-meta-history.xml.gz", "md5": "9660478d737bbed6c5fbf4a61a979dc9", "sha1": "260abb9fee17964ac9e35127cbd7307e876a7a8c"}, "enwiki-20240720-stub-meta-current.xml.gz": {"size": 6788744833, "url": "/enwiki/20240720/enwiki-20240720-stub-meta-current.xml.gz", "md5": "44927d4de920f4b7efc13a5178074cf2", "sha1": "8ca2e2a7225560a5b49eac1507d306a1bcb7d76a"}, "enwiki-20240720-stub-articles.xml.gz": {"size": 2902815267, "url": "/enwiki/20240720/enwiki-20240720-stub-articles.xml.gz", "md5": "1268303e60662a55675cf6cb2f6216e1", "sha1": "54bb1cf2da0872bc6af5d3e6e90a7a9d35e3a25a"}}}, "abstractsdumprecombine": {"status": "done", "updated": "2024-07-23 05:29:57", "files": {"enwiki-20240720-abstract.xml.gz": {"size": 881970148, "url": "/enwiki/20240720/enwiki-20240720-abstract.xml.gz", "md5": "58a82f8e30b8a2f883be7a3d4c04ddb3", "sha1": "58897e72575a5e28b9d75a5bdbd7e2a7caf91e13"}}}, "abstractsdump": {"status": "done", "updated": "2024-07-23 05:29:01", "files": {"enwiki-20240720-abstract1.xml.gz": {"size": 127232694, "url": "/enwiki/20240720/enwiki-20240720-abstract1.xml.gz", "md5": "0e900208e34a4ac1c84080c75484f608", "sha1": "a9cf5d44a84cc6a9ea1ca2e190a219e8e6b58bb6"}, "enwiki-20240720-abstract2.xml.gz": {"size": 57542126, "url": "/enwiki/20240720/enwiki-20240720-abstract2.xml.gz", "md5": "e9534f2a6430fd6c8e34fee6c03c86e7", "sha1": "57a86e5321b1df91837e035eeba8585a74bc48bb"}}}}, "version": "0.8"}
```

<br />

* Mục tiêu của pipeline là ingest, transform dữ liệu semi-structured như trên thành structured data và lưu trữ tại datawarehouse.

![alt text](https://github.com/EdenHimmelB/simple-gcp-pipeline/blob/master/images/structured_data.png?raw=true)

## Architecture
### Requirements:
* OS: Debian
* IaaC: Docker, Terraform
* Tools: gcloud cli

![alt text](https://github.com/EdenHimmelB/simple-gcp-pipeline/blob/master/images/flows.png?raw=true)


## Reproduce

### 1. Fork và Clone Repository

### 2. Thay đổi env variables cho pipeline.
Tại 2 file
* .env
* terraform/variables.tf

### 3. Đăng nhập và khởi tạo cloud infra

```
gcloud auth application-default login
```
Đăng nhập google cloud để có thể sử dụng terraform thao tác với môi trường cloud.

```
cd simple-gcp-pipeline/terraform/
terraform init
terraform apply
```
terraform apply sẽ enable tất cả APIs cần thiết cho project cùng với cloud infra cần thiết. Bên cạnh đó, terraform còn download google_application_credentials.json để airflow và spark có thể thao tác với cloud.


### 4. Build airflow và spark để orchestrate task và process data.
```
cd ..
docker compose build
docker compose up -d
```

### 5. Run pipeline

* Truy cập Airflow UI tại [http://localhost:8080/home](http://localhost:8080/home)
* Run pipeline manually.

![alt text](https://github.com/EdenHimmelB/simple-gcp-pipeline/blob/master/images/dag.png?raw=true)

*Pipeline chưa được test run do không còn free credit trên GCP :(*

### 6. Clean up cloud infra

```
cd terraform/
terraform destroy
```

Dọn hạ tầng trên cloud cùng với file **keys/google_application_credentials.json** tại local.
