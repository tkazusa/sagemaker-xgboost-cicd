import os
import uuid
import logging
import argparse

import stepfunctions
import boto3
import sagemaker
from sagemaker import get_execution_role
from sagemaker.estimator import Estimator
from sagemaker.session import s3_input
from sagemaker.amazon.amazon_estimator import get_image_uri

from stepfunctions import steps
from stepfunctions.inputs import ExecutionInput
from stepfunctions.workflow import Workflow

stepfunctions.set_stream_logger(level=logging.INFO)
id = uuid.uuid4().hex

REGION='us-east-1'
BUCKET='<データを準備した際に指定したバケット>'
FLOW_NAME='flow_{}'.format(id) 
TRAINING_JOB_NAME='sf-train-{}'.format(id) # To avoid duplication of job name
GLUE_ROLE = '<your-glue-role>'
SAGEMAKER_ROLE = '<your-sagemaker-role>'
WORKFLOW_ROLE='<your-stepfunctions-role>'


s3 = boto3.resource('s3')
session = sagemaker.Session()


if __name__ == '__main__':
    # flow.yaml の定義を環境変数経由で受け取る
    # buildspec.yaml の env.variables へ直接書き込んでも良いかも
    #parser = argparse.ArgumentParser()
    #parser.add_argument('--data_path', type=str, default=os.environ['DATA_PATH'])
    #args = parser.parse_args()


    # SFn の実行に必要な情報を渡す際のスキーマを定義します
    execution_input = ExecutionInput(schema={
        # AWS Glue
        'bucket_name': str,

        # SageMaker
        'TrainJobName': str,
        }
    )

    # SFn のワークフローの定義を記載します
    inputs={
         # AWS Glue
        'bucket_name': BUCKET,
        # SageMaker Training
        'TrainJobName': TRAINING_JOB_NAME
        }



    # それぞれのステップを定義していきます
    ## AWS Glue の job を Submit するステップ
    # バケットへの preprocess.py のアップロード
    s3.Object(BUCKET, 'preprocess.py').upload_file('preprocess.py')
    print('s3://{} へ Glue のスクリプトがアップロードされました。'.format(BUCKET))

    # Glue のジョブを作成します。
    glue = boto3.client('glue')
    job = glue.create_job(
                        Name='preprocess',
                        Role=GLUE_ROLE,
                        Command={'Name': 'pythonshell',
                               'ScriptLocation': 's3://{}/preprocess.py'.format(BUCKET),
                               'PythonVersion': '3'}
                        )

    etl_step = steps.GlueStartJobRunStep(
        state_id='GlueDataProcessingStep',
        parameters={
            'JobName': job['Name'],
            'Arguments': {
                '--bucket_name': execution_input['bucket_name'],
                }
            }
        )


    # データのパスを指定
    input_train = 's3://{}/train.csv'.format(BUCKET)
    input_validation = 's3://{}/validation.csv'.format(BUCKET)

    s3_input_train = s3_input(s3_data=input_train, content_type='text/csv')
    s3_input_validation = s3_input(s3_data=input_validation, content_type='text/csv')

    container = get_image_uri(boto3.Session().region_name, 'xgboost')
    hyperparameters = {
            "max_depth": "5",
            "eta": "0.2",
            "gamma": "4",
            "min_child_weight": "6",
            "subsample": "0.8",
            "silent": "0",
            "objective": "reg:linear",
            "num_round": "100"
            }
    
    xgb = sagemaker.estimator.Estimator(
        container,
        hyperparameters=hyperparameters,
        role=SAGEMAKER_ROLE,
        train_instance_count = 1,
        train_instance_type = 'ml.m4.4xlarge',
        train_volume_size = 5,
        sagemaker_session = session
    )

    training_step = steps.TrainingStep(
        'Train Step', 
        estimator=xgb,
        data={
            'train': s3_input_train, 
            'validation': s3_input_validation
        },
        job_name=execution_input['TrainJobName'],  
        wait_for_completion=True 
    )

    # このあと model_step/batch_tramsformStep: https://towardsdatascience.com/automating-machine-learning-workflows-with-aws-glue-sagemaker-and-aws-step-functions-data-science-b4ed59e4d7f9
    # 各 Step を連結
    chain_list = [etl_step, training_step]
    workflow_definition = steps.Chain(chain_list)

    # Workflow の作成
    workflow = Workflow(
        name=FLOW_NAME,
        definition=workflow_definition,
        role=WORKFLOW_ROLE,
        execution_input=execution_input,
    )
    workflow.create()

    # Workflow の実行
    execution = workflow.execute(inputs=inputs)