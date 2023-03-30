from aws_cdk import (
    # Duration,
    Stack,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_lambda as _lambda,
    Duration
)
from constructs import Construct

class MondayStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here
        
        # create a new IAM role for the Lambda function
        sfn_role = iam.Role(
            self, 'SFNIAMRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            role_name='StartStepFunctionLambdaRole',
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole')
            ]
        )
        sfn_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'logs:CreateLogGroup',
                    'logs:CreateLogStream',
                    'logs:PutLogEvents',
                    'states:StartExecution',
                    "events:PutEvents",
                    "workdocs:InitiateDocumentVersionUpload",
                    "workdocs:UpdateDocumentVersion",
                    "s3:GetObject"
                ],
                resources=['*']
            )
        )

        workdoc_role = iam.Role(
            self, 'WorkdocLambdaIAMRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            role_name='WorkdocLambdaRole',
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole')
            ]
        )
        workdoc_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'logs:CreateLogGroup',
                    'logs:CreateLogStream',
                    'logs:PutLogEvents',
                    "events:PutEvents",
                    "workdocs:InitiateDocumentVersionUpload",
                    "workdocs:UpdateDocumentVersion",
                    "s3:GetObject"
                ],
                resources=['*']
            )
        )

        execute_sf_lambda= _lambda.Function(self, "startstepfunctionlambda",
                                                       function_name="start_stepfunction_lambda",
                                                       handler="lambda_function.lambda_handler",
                                                       runtime=_lambda.Runtime.PYTHON_3_9,
                                                       code=_lambda.Code.from_asset(
                                                           "lambda/execute_lambda"),
                                                       timeout=Duration.seconds(10),
                                                       environment={
                                                            "StateMachine":"Woocommerce_state_machine"
                                                       },
                                                       role=sfn_role)
        webhook_lambda= _lambda.Function(self, "WebhookLambdaFunction",
                                                       function_name="Workdocs_lambda",
                                                       handler="lambda_function.lambda_handler",
                                                       runtime=_lambda.Runtime.PYTHON_3_9,
                                                       code=_lambda.Code.from_asset(
                                                           "lambda/webhook_lambda"),
                                                       timeout=Duration.seconds(10),
                                                       role=workdoc_role)



        execute_sf_task = tasks.LambdaInvoke(
            self,
            "ExecuteStepFunctionTask",
            lambda_function=webhook_lambda
        )

        execute_sf_state = execute_sf_task.next(sfn.Pass(self, "End of execution"))

        scan_state_machine=sfn.StateMachine(self, "StateMachine",
            state_machine_name="Woocommerce_state_machine",
            state_machine_type=sfn.StateMachineType.STANDARD,
            definition=execute_sf_state,
            timeout=Duration.minutes(5),
            tracing_enabled=True
        ) 
        api = apigw.RestApi(
            self,
            "StepFunctionAPI",
            rest_api_name="WoocommerceAPI"
        )

        execute_resource = api.root.add_resource("order")
        execute_method = execute_resource.add_method(
            "POST",
            apigw.LambdaIntegration(execute_sf_lambda),
            request_models={'application/json': apigw.Model.EMPTY_MODEL}
        )

