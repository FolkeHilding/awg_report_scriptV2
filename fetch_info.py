import boto3

def get_info_list():
    dynamodb = boto3.client('dynamodb', region_name='eu-north-1')
    table_name = "Items"
    combined_list = []
    
    try:
        response = dynamodb.query(
            TableName=table_name,
            IndexName='GSI1',
            KeyConditionExpression="GSI1PK = :pk",
            ExpressionAttributeValues={":pk": {"S": "ALL_DEVICES"}}
        )
        for item in response.get('Items', []):
            # Must be a 'next' model
            if item.get('model', {}).get('S', '').lower() != 'next':
                continue
                
            model_id = item.get('name', {}).get('S', '')
            if not model_id:
                continue
                
            # Safely handle empty strings for adminPrefName
            pref_name = item.get('adminPrefName', {}).get('S', '').strip() or model_id
            
            # Use serviceContact for all communications
            service_contact = item.get('serviceContact', {}).get('S', '').strip()
            
            parts = [model_id, pref_name]
            if service_contact:
                parts.append(service_contact)
                
            combined_entry = ", ".join(parts)
            combined_list.append(combined_entry)
            
    except Exception as e:
        print(f"Error fetching info list: {e}")
        
    return combined_list

def get_single_prefName(model):
    """Replaces the old tmp.py API Gateway lookup with a direct, fast DynamoDB lookup."""
    dynamodb = boto3.client('dynamodb', region_name='eu-north-1')
    try:
        response = dynamodb.get_item(
            TableName="Items",
            Key={
                "PK": {"S": f"DEVICE#{model}#next"},
                "SK": {"S": "METADATA"}
            }
        )
        item = response.get('Item', {})
        return item.get('adminPrefName', {}).get('S', '').strip() or model
    except Exception as e:
        print(f"Error fetching prefName for {model}: {e}")
        return model

if __name__ == "__main__":
    print(get_info_list())