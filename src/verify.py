import json
import os
import boto3
from typing import Dict, Any

dynamodb = boto3.client('dynamodb')
sns = boto3.client('sns')

TABLE_NAME = os.environ.get('RECEIPT_TABLE', 'AgentGuardReceipts')
SNS_TOPIC_ARN = os.environ.get('ALERT_TOPIC_ARN')

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AgentGuard Verify: Validates an agent's claimed tool output against the cryptographic receipt.
    If the agent hallucinated the output, this detects the divergence and blocks downstream execution.
    """
    try:
        body = json.loads(event.get('body', '{}'))
        receipt_hash = body.get('receipt_hash')
        claimed_output = body.get('claimed_output', {})
        agent_id = body.get('agent_id')
        
        if not receipt_hash:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing receipt_hash'})
            }

        # Fetch the authoritative receipt from DynamoDB
        response = dynamodb.get_item(
            TableName=TABLE_NAME,
            Key={'ReceiptHash': {'S': receipt_hash}}
        )
        
        item = response.get('Item')
        if not item:
            trigger_hallucination_alert(agent_id, receipt_hash, "Fabricated Receipt", claimed_output)
            return {
                'statusCode': 403,
                'body': json.dumps({'verified': False, 'reason': 'Receipt not found. Potential complete hallucination.'})
            }

        actual_output_str = item['OutputPayload']['S']
        claimed_output_str = json.dumps(claimed_output, sort_keys=True)
        
        # Verify the claimed output matches the cryptographic record
        if actual_output_str != claimed_output_str:
            trigger_hallucination_alert(agent_id, receipt_hash, "Output Divergence", claimed_output, actual_output_str)
            return {
                'statusCode': 403,
                'body': json.dumps({
                    'verified': False, 
                    'reason': 'Claimed output diverges from authoritative receipt. Hallucination detected.'
                })
            }

        return {
            'statusCode': 200,
            'body': json.dumps({'verified': True, 'status': item['Status']['S']})
        }

    except Exception as e:
        print(f"Error during verification: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error during verification'})
        }

def trigger_hallucination_alert(agent_id: str, receipt_hash: str, violation_type: str, claimed: Any, actual: str = "N/A"):
    """Alert the security/engineering team that an agent attempted to pass fabricated data."""
    if not SNS_TOPIC_ARN:
        return
        
    message = {
        'alert_type': 'AGENT_HALLUCINATION_DETECTED',
        'violation_type': violation_type,
        'agent_id': agent_id,
        'receipt_hash': receipt_hash,
        'claimed_output': claimed,
        'actual_authoritative_output': actual,
        'action_taken': 'Downstream execution blocked'
    }
    
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"CRITICAL: AgentGuard detected hallucination [{agent_id}]",
        Message=json.dumps(message, indent=2)
    )
