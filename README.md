# Amazon SageMaker での CI/CD デモ

## 準備
### Step1. *SageMaker notebook を作成する*
SageMaker ノートブックインスタンスを立ち上げる

- ロールを新規に作成し、任意の S3 バケットへのアクセス権限を付与する。
- `Clone a public Git repository to this notebook instance only`  を選択し、このリポジトリをクローンする。
- ノートブックインスタンスが ‘InService’ になったら、JupyterLab を開く
- `dataprep.ipynb` を実行し、使用するバケット名を保存する。

### Step2. IAM ロールを作成する
- AWS Glue の IAMロール
    - ポリシー: AWSGlueServiceRole, S3FullAccess
- SageMaker のIAMロール
    - AWSStepFunctionsFullAccess
    - AmazonSageMakerFullAccess
- AWS StepFunctions の IAMロール
    - AWSGlueServiceRole
    - AmazonSageMakerFullAccess
    - AWSStepFunctionsFullAccess




### Step.4 CodeBuild のビルドプロジェクトを作成する
- プロジェクト名: sagemaker-xgboost-cicd
- ソースプロバイダ: Github
    - GitHub アカウントのリポジトリ：sagemaker-xgboost-cicd を指定
- プライマリソースのウェブフックイベント
    - コードの変更がこのレポジトリにプッシュされるたびに再構築する
    - イベントタイプ：PULL_REQUEST_CREATED、PULL_REQUEST_UPDATED
    - Start a build under these conditions HEAD_REF : ^refs/heads/model-dev$
- 環境：マネージド型イメージ
    - オペレーティングシステム：Ubuntu
    - ランタイム:Standard
    - イメージ:aws/codebuild/standard:3.0
    - イメージのバージョン:aws/codebuild/standard:3.0-20.05.05
    - 環境タイプ:Linux
    - サービスロール: 新規のロールを作成する
- Buildspec
    - buildspec.yaml を指定


### Step.5 CodeBuild の IAM ロールを編集する
- ビルドプロジェクト作成時に作成したロールをへ下記ポリシーを追加する。
    - StepFunctionsFullAccess
    - AWSCodebuildDeveloperAccess
    - AmazonS3FullAccess
    - AWSGlueServiceRole
- 下記ポリシーを作成して追加する。
```JSON
{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Action": [
				"iam:PassRole"
			],
			"Effect": "Allow",
			"Resource": "*"
		}
	]
}
```

## 実行手順
- SageMaker ノートブックインスタスにて JupyterLab を開く。
- ターミナルを軌道して、新しいブランチ `model-dev` を作成し、チェックイン。
```
$ cd SageMaker/
$ git checkout -b model-dev
```
- `pipeline.py` 中の下記項目を記載する。
```
BUCKET='<データを準備した際に指定したバケット>'
FLOW_NAME='flow_{}'.format(id) 
TRAINING_JOB_NAME='sf-train-{}'.format(id) # To avoid duplication of job name
GLUE_ROLE = '<your-glue-role>'
SAGEMAKER_ROLE = '<your-sagemaker-role>'
WORKFLOW_ROLE='<your-stepfunctions-role>'
```
- git 上で変更を反映させる。
```
$ git add pipeline.py
$ git commit -m “mod demo.txt”
$ git push origin HEAD
```

- GitHub リポジトリ上で Pull Request を作成する。


