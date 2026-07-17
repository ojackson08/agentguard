import json
import os
import time
import hashlib
import boto3
from typing import Dict, Any

# Initialize AWS clients
dynamodb = boto3.client('dynamodb')
sns = boto3.client('sns')

TABLE_NAME = os.environ.get('RECEIPT_TABLE', 'AgentGuardReceipts')
SNS_TOPIC_ARN = os.environ.get('ALERT_TOPIC_ARN')

def generate_receipt_hash(agent_id: str, tool_name: str, input_payload: str, output_payload: str, timestamp: int) -> str:
    """Generate a cryptographic hash for the tool execution receipt."""
    content = f"{agent_id}:{tool_name}:{input_payload}:{output_payload}:{timestamp}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AgentGuard Proxy: Intercepts tool calls, executes them, and stamps a cryptographic receipt.
    This prevents agents from hallucinating tool outputs by enforcing a verifiable audit trail.
    """
    try:
        # Parse incoming request from agent
        body = json.loads(event.get('body', '{}'))
        agent_id = body.get('agent_id')
        tool_name = body.get('tool_name')
        tool_input = body.get('tool_input', {})
        
        if not all([agent_id, tool_name]):
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required fields: agent_id, tool_name'})
            }

        timestamp = int(time.time())
        input_str = json.dumps(tool_input, sort_keys=True)
        
        # In a real deployment, this would dynamically route to the actual tool endpoint
        # For this architecture demonstration, we simulate the tool execution
        tool_output, is_error = simulate_tool_execution(tool_name, tool_input)
        output_str = json.dumps(tool_output, sort_keys=True)
        
        # Generate cryptographic receipt
        receipt_hash = generate_receipt_hash(agent_id, tool_name, input_str, output_str, timestamp)
        
        # Store receipt in DynamoDB
        store_receipt(agent_id, tool_name, input_str, output_str, receipt_hash, timestamp, is_error)
        
        # Alert if the tool failed but returned a clean empty payload (silent failure risk)
        if is_error or not tool_output:
            alert_silent_failure_risk(agent_id, tool_name, receipt_hash)

        return {
            'statusCode': 200 if not is_error else 500,
            'body': json.dumps({
                'receipt_hash': receipt_hash,
                'tool_output': tool_output,
                'status': 'error' if is_error else 'success'
            })
        }

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error during tool proxy execution'})
        }

def simulate_tool_execution(tool_name: str, tool_input: Dict) -> tuple[Dict, bool]:
    """Simulate actual tool execution. Returns (output_dict, is_error_boolean)"""
    if tool_name == 'database_query':
        if tool_input.get('query') == 'SELECT * FROM users':
            return {'users': ['alice', 'bob']}, False
        return {}, True # Simulate empty/failed result
    return {'result': f'Executed {tool_name}'}, False

def store_receipt(agent_id: str, tool_name: str, input_str: str, output_str: str, receipt_hash: str, timestamp: int, is_error: bool):
    """Store the cryptographic receipt in DynamoDB for downstream verification."""
    dynamodb.put_item(
        TableName=TABLE_NAME,
        Item={
            'ReceiptHash': {'S': receipt_hash},
            'AgentId': {'S': agent_id},
            'ToolName': {'S': tool_name},
            'InputPayload': {'S': input_str},
            'OutputPayload': {'S': output_str},
            'Timestamp': {'N': str(timestamp)},
            'Status': {'S': 'ERROR' if is_error else 'SUCCESS'}
        }
    )

def alert_silent_failure_risk(agent_id: str, tool_name: str, receipt_hash: str):
    """Fire SNS alert for potential silent failures where downstream agents might hallucinate success."""
    if not SNS_TOPIC_ARN:
        return
        
    message = {
        'alert_type': 'SILENT_FAILURE_RISK',
        'agent_id': agent_id,
        'tool_name': tool_name,
        'receipt_hash': receipt_hash,
        'description': 'Tool returned empty or error state. Downstream verification required to ensure agent does not hallucinate a successful result.'
    }
    
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"AgentGuard Alert: Tool Failure Risk [{agent_id}]",
        Message=json.dumps(message)
    )
