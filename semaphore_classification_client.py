import requests
import json
import os
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

class SemaphoreClassificationClient:
    """
    Python client for the Semaphore Classification Service.
    
    This client handles authentication and text classification using the Semaphore
    Classification Service provided by Progress Cloud.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Semaphore Classification Client.
        
        Args:
            api_key (str, optional): Your Semaphore API key. If not provided, 
                                   will try to load from SEMAPHORE_API_KEY environment variable.
        """
        load_dotenv()
        
        self.api_key = api_key or os.getenv('SEMAPHORE_API_KEY')
        if not self.api_key:
            raise ValueError("API key required. Provide directly or set SEMAPHORE_API_KEY env var.")
        
        self.base_url = "https://icaew.data.progress.cloud"
        self.token_url = f"{self.base_url}/token/"
        self.classification_url = f"{self.base_url}/cls/prod/cs/"
        self.alternative_classification_url = f"{self.base_url}/classification/"
        
        self.access_token = None
    
    def authenticate(self) -> str:
        """
        Generate an authentication token for the session.
        
        Returns:
            str: The access token for subsequent API calls.
            
        Raises:
            requests.RequestException: If authentication fails.
        """
        payload = {"key": self.api_key, "grantType": "apikey"}
        response = requests.post(self.token_url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data.get("access_token")
        if not self.access_token:
            raise ValueError("No access token received")
        return self.access_token
    
    def classify_text(self, text: str, title: Optional[str] = None, threshold: Optional[int] = None, 
                     language: Optional[str] = None, use_alternative_endpoint: bool = False) -> Dict[str, Any]:
        """
        Classify text using the Semaphore Classification Service with optional parameters.
        
        Args:
            text (str): The text to classify.
            title (str, optional): The title of the document.
            threshold (int, optional): The threshold for classification.
            language (str, optional): The language of the document.
            use_alternative_endpoint (bool): Whether to use the alternative 
                                           classification endpoint.
        
        Returns:
            dict: The classification results in XML format (parsed as dict).
            
        Raises:
            requests.RequestException: If classification request fails.
            ValueError: If no access token is available.
        """
        if not self.access_token:
            self.authenticate()
        
        endpoint = self.alternative_classification_url if use_alternative_endpoint else self.classification_url
        headers = {"Authorization": f"bearer {self.access_token}"}
        
        data = {"body": text}
        if title:
            data["title"] = title
        if threshold:
            data["threshold"] = str(threshold)
        if language:
            data["language"] = language
        
        response = requests.post(endpoint, data=data, headers=headers)
        response.raise_for_status()
        
        try:
            return response.json()
        except json.JSONDecodeError:
            return {"raw_response": response.text}
    
    def classify_file(self, file_path: str, title: Optional[str] = None, threshold: Optional[int] = None,
                     language: Optional[str] = None, use_alternative_endpoint: bool = False) -> Dict[str, Any]:
        """
        Classify a file directly.
        
        Args:
            file_path (str): The path to the file to classify.
            title (str, optional): The title of the document.
            threshold (int, optional): The threshold for classification.
            language (str, optional): The language of the document.
            use_alternative_endpoint (bool): Whether to use the alternative 
                                           classification endpoint.
        
        Returns:
            dict: The classification results in XML format (parsed as dict).
            
        Raises:
            requests.RequestException: If classification request fails.
            ValueError: If no access token is available.
        """
        if not self.access_token:
            self.authenticate()
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        endpoint = self.alternative_classification_url if use_alternative_endpoint else self.classification_url
        headers = {"Authorization": f"bearer {self.access_token}"}
        
        with open(file_path, 'rb') as f:
            files = {"UploadFile": (os.path.basename(file_path), f, "application/octet-stream")}
            data = {}
            if title:
                data["title"] = title
            if threshold:
                data["threshold"] = str(threshold)
            if language:
                data["language"] = language
            
            response = requests.post(endpoint, files=files, data=data, headers=headers)
            response.raise_for_status()
        
        try:
            return response.json()
        except json.JSONDecodeError:
            return {"raw_response": response.text}
    
    def parse_classification_results(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse classification results into a structured format.
        
        Args:
            result (dict): The classification result in XML format.
        
        Returns:
            dict: The parsed classification results.
        """
        if 'raw_response' not in result:
            return result
        
        import re
        xml = result['raw_response']
        
        # Extract basic document info
        doc_info = {}
        doc_info['url'] = re.search(r'<URL>(.*?)</URL>', xml)
        doc_info['url'] = doc_info['url'].group(1) if doc_info['url'] else None
        
        # Extract all META fields with scores
        meta_fields = re.findall(r'<META name="([^"]+)" value="([^"]+)"(?: id="([^"]+)" score="([^"]+)")?', xml)
        classifications = {}
        for name, value, id_val, score in meta_fields:
            if name not in classifications:
                classifications[name] = []
            classifications[name].append({
                'value': value,
                'id': id_val if id_val else None,
                'score': float(score) if score else None
            })
        
        # Extract SYSTEM fields
        system_fields = re.findall(r'<SYSTEM name="([^"]+)" value="([^"]+)"', xml)
        system_info = {name: value for name, value in system_fields}
        
        return {
            'document_info': doc_info,
            'classifications': classifications,
            'system_info': system_info,
            'raw_xml': xml
        }
    
    def get_top_classifications(self, result: Dict[str, Any], max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Get top classifications sorted by score.
        
        Args:
            result (dict): The classification result in XML format.
            max_results (int): The maximum number of results to return.
        
        Returns:
            list: The top classifications sorted by score.
        """
        parsed = self.parse_classification_results(result)
        all_classifications = []
        
        for category, items in parsed['classifications'].items():
            for item in items:
                if item['score'] is not None:
                    all_classifications.append({
                        'category': category,
                        'value': item['value'],
                        'score': item['score'],
                        'id': item['id']
                    })
        
        # Sort by score descending and return top results
        all_classifications.sort(key=lambda x: x['score'], reverse=True)
        return all_classifications[:max_results]
    
    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the service endpoints.
        
        Returns:
            dict: Service information including endpoints and API key status.
        """
        return {
            "base_url": self.base_url,
            "token_url": self.token_url,
            "classification_url": self.classification_url,
            "api_key_configured": bool(self.api_key),
            "token_available": bool(self.access_token)
        }


def main():
    """
    Example usage of the Semaphore Classification Client.
    """
    print("🚀 Semaphore Classification Service Client")
    print("=" * 50)
    
    # Initialize client
    try:
        client = SemaphoreClassificationClient()
        print("✅ Client initialized successfully")
        
        # Display service info
        info = client.get_service_info()
        print(f"\n📋 Service Information:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        # Test authentication
        print(f"\n🔐 Testing authentication...")
        token = client.authenticate()
        print(f"  Token: {token[:20]}...")
        
        # Test classification
        print(f"\n📝 Testing classification...")
        test_text = "This is a sample text for classification testing."
        result = client.classify_text(test_text)
        print(f"  Result: {result}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main() 