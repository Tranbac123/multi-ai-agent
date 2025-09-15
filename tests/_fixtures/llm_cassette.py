"""LLM cassette recorder and golden output loader for deterministic testing."""

import json
import hashlib
import os
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from datetime import datetime
import re

from .factories import factory

class LLMCassetteRecorder:
    """Records LLM interactions for deterministic testing."""
    
    def __init__(self, cassette_dir: str = "tests/_fixtures/cassettes"):
        """Initialize cassette recorder."""
        self.cassette_dir = Path(cassette_dir)
        self.cassette_dir.mkdir(parents=True, exist_ok=True)
        self.recordings: Dict[str, Dict[str, Any]] = {}
    
    def normalize_prompt(self, prompt: str, **kwargs) -> str:
        """Normalize prompt for consistent hashing."""
        # Remove timestamps and dynamic content
        normalized = prompt
        
        # Replace timestamps with placeholder
        timestamp_pattern = r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}'
        normalized = re.sub(timestamp_pattern, '[TIMESTAMP]', normalized)
        
        # Replace UUIDs with placeholder
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        normalized = re.sub(uuid_pattern, '[UUID]', normalized)
        
        # Replace dynamic IDs with placeholders
        id_pattern = r'(?:tenant_|user_|doc_|cart_|pay_)\d{4}'
        normalized = re.sub(id_pattern, '[ID]', normalized)
        
        # Sort kwargs for consistent hashing
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            normalized += f"|{json.dumps(sorted_kwargs, sort_keys=True)}"
        
        return normalized
    
    def generate_key(self, prompt: str, model: str = "gpt-4", **kwargs) -> str:
        """Generate a unique key for the LLM interaction."""
        normalized_prompt = self.normalize_prompt(prompt, **kwargs)
        content = f"{model}:{normalized_prompt}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def record_interaction(
        self,
        prompt: str,
        response: str,
        model: str = "gpt-4",
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """Record an LLM interaction."""
        key = self.generate_key(prompt, model, **kwargs)
        
        recording = {
            'key': key,
            'prompt': prompt,
            'response': response,
            'model': model,
            'metadata': metadata or {},
            'kwargs': kwargs,
            'recorded_at': datetime.now().isoformat(),
            'normalized_prompt': self.normalize_prompt(prompt, **kwargs)
        }
        
        self.recordings[key] = recording
        
        # Save to file
        cassette_file = self.cassette_dir / f"{key}.json"
        with open(cassette_file, 'w') as f:
            json.dump(recording, f, indent=2)
        
        return key
    
    def load_recording(self, key: str) -> Optional[Dict[str, Any]]:
        """Load a recorded interaction."""
        if key in self.recordings:
            return self.recordings[key]
        
        cassette_file = self.cassette_dir / f"{key}.json"
        if cassette_file.exists():
            with open(cassette_file, 'r') as f:
                recording = json.load(f)
                self.recordings[key] = recording
                return recording
        
        return None
    
    def get_response(self, prompt: str, model: str = "gpt-4", **kwargs) -> Optional[str]:
        """Get a recorded response for a prompt."""
        key = self.generate_key(prompt, model, **kwargs)
        recording = self.load_recording(key)
        return recording['response'] if recording else None

class GoldenOutputLoader:
    """Loads and manages golden outputs for deterministic testing."""
    
    def __init__(self, golden_dir: str = "tests/_fixtures/golden"):
        """Initialize golden output loader."""
        self.golden_dir = Path(golden_dir)
        self.golden_dir.mkdir(parents=True, exist_ok=True)
        self.outputs: Dict[str, Any] = {}
    
    def normalize_output(self, output: Any) -> Any:
        """Normalize output for consistent comparison."""
        if isinstance(output, str):
            # Normalize whitespace and remove dynamic content
            normalized = re.sub(r'\s+', ' ', output.strip())
            
            # Replace timestamps with placeholder
            timestamp_pattern = r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}'
            normalized = re.sub(timestamp_pattern, '[TIMESTAMP]', normalized)
            
            # Replace UUIDs with placeholder
            uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
            normalized = re.sub(uuid_pattern, '[UUID]', normalized)
            
            return normalized
        
        elif isinstance(output, dict):
            return {k: self.normalize_output(v) for k, v in output.items()}
        
        elif isinstance(output, list):
            return [self.normalize_output(item) for item in output]
        
        else:
            return output
    
    def save_golden_output(
        self,
        test_name: str,
        output: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save a golden output."""
        normalized_output = self.normalize_output(output)
        
        golden_data = {
            'test_name': test_name,
            'output': normalized_output,
            'metadata': metadata or {},
            'saved_at': datetime.now().isoformat()
        }
        
        # Save to file
        golden_file = self.golden_dir / f"{test_name}.json"
        with open(golden_file, 'w') as f:
            json.dump(golden_data, f, indent=2)
        
        self.outputs[test_name] = golden_data
        return str(golden_file)
    
    def load_golden_output(self, test_name: str) -> Optional[Any]:
        """Load a golden output."""
        if test_name in self.outputs:
            return self.outputs[test_name]['output']
        
        golden_file = self.golden_dir / f"{test_name}.json"
        if golden_file.exists():
            with open(golden_file, 'r') as f:
                golden_data = json.load(f)
                self.outputs[test_name] = golden_data
                return golden_data['output']
        
        return None
    
    def compare_outputs(self, test_name: str, actual_output: Any) -> Dict[str, Any]:
        """Compare actual output with golden output."""
        golden_output = self.load_golden_output(test_name)
        
        if golden_output is None:
            return {
                'match': False,
                'error': 'No golden output found',
                'actual': actual_output
            }
        
        normalized_actual = self.normalize_output(actual_output)
        
        if normalized_actual == golden_output:
            return {'match': True, 'actual': normalized_actual}
        else:
            return {
                'match': False,
                'golden': golden_output,
                'actual': normalized_actual,
                'diff': self._compute_diff(golden_output, normalized_actual)
            }
    
    def _compute_diff(self, golden: Any, actual: Any) -> Dict[str, Any]:
        """Compute difference between golden and actual outputs."""
        if golden == actual:
            return {}
        
        if isinstance(golden, dict) and isinstance(actual, dict):
            diff = {}
            all_keys = set(golden.keys()) | set(actual.keys())
            
            for key in all_keys:
                if key not in golden:
                    diff[key] = {'added': actual[key]}
                elif key not in actual:
                    diff[key] = {'removed': golden[key]}
                else:
                    key_diff = self._compute_diff(golden[key], actual[key])
                    if key_diff:
                        diff[key] = key_diff
            
            return diff
        
        elif isinstance(golden, list) and isinstance(actual, list):
            if len(golden) != len(actual):
                return {'length_mismatch': {'golden': len(golden), 'actual': len(actual)}}
            
            diff = []
            for i, (g_item, a_item) in enumerate(zip(golden, actual)):
                item_diff = self._compute_diff(g_item, a_item)
                if item_diff:
                    diff.append({'index': i, 'diff': item_diff})
            
            return {'items': diff} if diff else {}
        
        else:
            return {'type_mismatch': {'golden': type(golden), 'actual': type(actual)}}

# Global instances
cassette_recorder = LLMCassetteRecorder()
golden_loader = GoldenOutputLoader()

# Helper functions for easy access
def record_llm_interaction(prompt: str, response: str, model: str = "gpt-4", **kwargs) -> str:
    """Record an LLM interaction."""
    return cassette_recorder.record_interaction(prompt, response, model, **kwargs)

def get_llm_response(prompt: str, model: str = "gpt-4", **kwargs) -> Optional[str]:
    """Get a recorded LLM response."""
    return cassette_recorder.get_response(prompt, model, **kwargs)

def save_golden_output(test_name: str, output: Any, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Save a golden output."""
    return golden_loader.save_golden_output(test_name, output, metadata)

def load_golden_output(test_name: str) -> Optional[Any]:
    """Load a golden output."""
    return golden_loader.load_golden_output(test_name)

def compare_with_golden(test_name: str, actual_output: Any) -> Dict[str, Any]:
    """Compare actual output with golden output."""
    return golden_loader.compare_outputs(test_name, actual_output)
