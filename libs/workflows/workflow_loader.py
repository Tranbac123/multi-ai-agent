"""WorkflowSpec loader with fragments and overlays support."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from uuid import UUID
import structlog
from dataclasses import dataclass

logger = structlog.get_logger(__name__)


@dataclass
class WorkflowStep:
    """Workflow step definition."""
    id: str
    type: str
    name: str
    config: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowTransition:
    """Workflow transition definition."""
    from_step: str
    to_step: str
    condition: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowSpec:
    """Complete workflow specification."""
    name: str
    version: str
    description: str
    settings: Dict[str, Any]
    steps: List[WorkflowStep]
    transitions: List[WorkflowTransition]
    tools: List[Dict[str, Any]]
    error_handling: List[Dict[str, Any]]
    metrics: List[Dict[str, Any]]
    feature_flags: Optional[Dict[str, Any]] = None
    quotas: Optional[Dict[str, Any]] = None
    security: Optional[Dict[str, Any]] = None
    monitoring: Optional[Dict[str, Any]] = None


class WorkflowLoader:
    """Loads and merges workflow specifications with fragments and overlays."""
    
    def __init__(self, base_path: str = "configs/workflows"):
        self.base_path = Path(base_path)
        self.cache: Dict[str, WorkflowSpec] = {}
    
    def load_workflow(
        self,
        workflow_name: str,
        tenant_id: Optional[UUID] = None,
        environment: str = "production"
    ) -> WorkflowSpec:
        """Load workflow with tenant and environment overrides."""
        cache_key = f"{workflow_name}:{tenant_id}:{environment}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Load base workflow
            base_spec = self._load_base_workflow(workflow_name)
            
            # Apply tenant overrides if specified
            if tenant_id:
                tenant_spec = self._load_tenant_workflow(tenant_id, workflow_name)
                if tenant_spec:
                    base_spec = self._merge_specs(base_spec, tenant_spec)
            
            # Apply environment overrides
            env_spec = self._load_environment_workflow(environment, workflow_name)
            if env_spec:
                base_spec = self._merge_specs(base_spec, env_spec)
            
            # Validate final specification
            self._validate_spec(base_spec)
            
            # Cache the result
            self.cache[cache_key] = base_spec
            
            logger.info("Workflow loaded", 
                       workflow_name=workflow_name, 
                       tenant_id=tenant_id,
                       environment=environment)
            
            return base_spec
            
        except Exception as e:
            logger.error("Failed to load workflow", 
                        workflow_name=workflow_name, 
                        error=str(e))
            raise
    
    def _load_base_workflow(self, workflow_name: str) -> WorkflowSpec:
        """Load base workflow specification."""
        # Try to load from usecases first
        usecase_path = self.base_path / "usecases" / f"{workflow_name}.yaml"
        if usecase_path.exists():
            return self._load_yaml_spec(usecase_path)
        
        # Fall back to base
        base_path = self.base_path / "base" / f"{workflow_name}.yaml"
        if base_path.exists():
            return self._load_yaml_spec(base_path)
        
        raise FileNotFoundError(f"Workflow {workflow_name} not found")
    
    def _load_tenant_workflow(self, tenant_id: UUID, workflow_name: str) -> Optional[WorkflowSpec]:
        """Load tenant-specific workflow overrides."""
        tenant_path = self.base_path / "tenants" / f"{tenant_id}.yaml"
        if not tenant_path.exists():
            # Try default tenant
            tenant_path = self.base_path / "tenants" / "default.yaml"
            if not tenant_path.exists():
                return None
        
        return self._load_yaml_spec(tenant_path)
    
    def _load_environment_workflow(self, environment: str, workflow_name: str) -> Optional[WorkflowSpec]:
        """Load environment-specific workflow overrides."""
        env_path = self.base_path / "environments" / f"{environment}.yaml"
        if not env_path.exists():
            return None
        
        return self._load_yaml_spec(env_path)
    
    def _load_yaml_spec(self, file_path: Path) -> WorkflowSpec:
        """Load workflow specification from YAML file."""
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Handle extends directive
        if 'extends' in data:
            base_spec = self._load_yaml_spec(self.base_path / data['extends'])
            extended_spec = self._merge_specs(base_spec, data)
            return extended_spec
        
        # Handle mutations
        if 'mutations' in data:
            spec = self._apply_mutations(data)
        else:
            spec = data
        
        return self._parse_spec(spec)
    
    def _apply_mutations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply mutations to workflow specification."""
        spec = data.copy()
        mutations = spec.pop('mutations', [])
        
        for mutation in mutations:
            mutation_type = mutation.get('type')
            target = mutation.get('target')
            
            if mutation_type == 'insert_after':
                self._insert_after(spec, target, mutation.get('step'))
            elif mutation_type == 'insert_before':
                self._insert_before(spec, target, mutation.get('step'))
            elif mutation_type == 'replace':
                self._replace_step(spec, target, mutation.get('step'))
            elif mutation_type == 'remove':
                self._remove_step(spec, target)
            elif mutation_type == 'enable':
                self._enable_feature(spec, mutation.get('feature'))
            elif mutation_type == 'disable':
                self._disable_feature(spec, mutation.get('feature'))
        
        return spec
    
    def _insert_after(self, spec: Dict[str, Any], target: str, step: Dict[str, Any]):
        """Insert step after target step."""
        steps = spec.get('workflow', {}).get('steps', [])
        target_index = self._find_step_index(steps, target)
        
        if target_index is not None:
            steps.insert(target_index + 1, step)
    
    def _insert_before(self, spec: Dict[str, Any], target: str, step: Dict[str, Any]):
        """Insert step before target step."""
        steps = spec.get('workflow', {}).get('steps', [])
        target_index = self._find_step_index(steps, target)
        
        if target_index is not None:
            steps.insert(target_index, step)
    
    def _replace_step(self, spec: Dict[str, Any], target: str, step: Dict[str, Any]):
        """Replace target step with new step."""
        steps = spec.get('workflow', {}).get('steps', [])
        target_index = self._find_step_index(steps, target)
        
        if target_index is not None:
            steps[target_index] = step
    
    def _remove_step(self, spec: Dict[str, Any], target: str):
        """Remove target step."""
        steps = spec.get('workflow', {}).get('steps', [])
        target_index = self._find_step_index(steps, target)
        
        if target_index is not None:
            steps.pop(target_index)
    
    def _enable_feature(self, spec: Dict[str, Any], feature: str):
        """Enable feature flag."""
        if 'feature_flags' not in spec:
            spec['feature_flags'] = {}
        spec['feature_flags'][feature] = True
    
    def _disable_feature(self, spec: Dict[str, Any], feature: str):
        """Disable feature flag."""
        if 'feature_flags' not in spec:
            spec['feature_flags'] = {}
        spec['feature_flags'][feature] = False
    
    def _find_step_index(self, steps: List[Dict[str, Any]], step_id: str) -> Optional[int]:
        """Find step index by ID."""
        for i, step in enumerate(steps):
            if step.get('id') == step_id:
                return i
        return None
    
    def _merge_specs(self, base: WorkflowSpec, override: Dict[str, Any]) -> WorkflowSpec:
        """Merge workflow specifications."""
        # Convert base to dict for merging
        base_dict = {
            'name': base.name,
            'version': base.version,
            'description': base.description,
            'workflow': {
                'settings': base.settings,
                'steps': [self._step_to_dict(step) for step in base.steps],
                'transitions': [self._transition_to_dict(trans) for trans in base.transitions],
                'tools': base.tools,
                'error_handling': base.error_handling,
                'metrics': base.metrics
            }
        }
        
        if base.feature_flags:
            base_dict['feature_flags'] = base.feature_flags
        if base.quotas:
            base_dict['quotas'] = base.quotas
        if base.security:
            base_dict['security'] = base.security
        if base.monitoring:
            base_dict['monitoring'] = base.monitoring
        
        # Deep merge
        merged = self._deep_merge(base_dict, override)
        
        return self._parse_spec(merged)
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _parse_spec(self, data: Dict[str, Any]) -> WorkflowSpec:
        """Parse workflow specification from dictionary."""
        workflow_data = data.get('workflow', {})
        
        # Parse steps
        steps = []
        for step_data in workflow_data.get('steps', []):
            step = WorkflowStep(
                id=step_data['id'],
                type=step_data['type'],
                name=step_data['name'],
                config=step_data.get('config', {}),
                metadata=step_data.get('metadata')
            )
            steps.append(step)
        
        # Parse transitions
        transitions = []
        for trans_data in workflow_data.get('transitions', []):
            transition = WorkflowTransition(
                from_step=trans_data['from'],
                to_step=trans_data['to'],
                condition=trans_data['condition'],
                metadata=trans_data.get('metadata')
            )
            transitions.append(transition)
        
        return WorkflowSpec(
            name=data.get('name', ''),
            version=data.get('version', '1.0.0'),
            description=data.get('description', ''),
            settings=workflow_data.get('settings', {}),
            steps=steps,
            transitions=transitions,
            tools=workflow_data.get('tools', []),
            error_handling=workflow_data.get('error_handling', []),
            metrics=workflow_data.get('metrics', []),
            feature_flags=data.get('feature_flags'),
            quotas=data.get('quotas'),
            security=data.get('security'),
            monitoring=data.get('monitoring')
        )
    
    def _step_to_dict(self, step: WorkflowStep) -> Dict[str, Any]:
        """Convert step to dictionary."""
        result = {
            'id': step.id,
            'type': step.type,
            'name': step.name,
            'config': step.config
        }
        if step.metadata:
            result['metadata'] = step.metadata
        return result
    
    def _transition_to_dict(self, transition: WorkflowTransition) -> Dict[str, Any]:
        """Convert transition to dictionary."""
        result = {
            'from': transition.from_step,
            'to': transition.to_step,
            'condition': transition.condition
        }
        if transition.metadata:
            result['metadata'] = transition.metadata
        return result
    
    def _validate_spec(self, spec: WorkflowSpec):
        """Validate workflow specification."""
        # Check required fields
        if not spec.name:
            raise ValueError("Workflow name is required")
        
        if not spec.steps:
            raise ValueError("Workflow must have at least one step")
        
        # Check step IDs are unique
        step_ids = [step.id for step in spec.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Step IDs must be unique")
        
        # Check transitions reference valid steps
        step_id_set = set(step_ids)
        for transition in spec.transitions:
            if transition.from_step not in step_id_set:
                raise ValueError(f"Transition references unknown step: {transition.from_step}")
            if transition.to_step not in step_id_set and transition.to_step != "end":
                raise ValueError(f"Transition references unknown step: {transition.to_step}")
        
        # Validate step configurations
        for step in spec.steps:
            self._validate_step(step)
    
    def _validate_step(self, step: WorkflowStep):
        """Validate individual step."""
        if not step.id:
            raise ValueError("Step ID is required")
        
        if not step.type:
            raise ValueError("Step type is required")
        
        if not step.name:
            raise ValueError("Step name is required")
        
        # Validate step-specific configurations
        if step.type == "validator" and "schema" not in step.config:
            raise ValueError("Validator steps must have a schema")
        
        if step.type == "tool_call" and "tool" not in step.config:
            raise ValueError("Tool call steps must specify a tool")
    
    def clear_cache(self):
        """Clear workflow cache."""
        self.cache.clear()
        logger.info("Workflow cache cleared")
    
    def get_cached_workflows(self) -> List[str]:
        """Get list of cached workflow names."""
        return list(self.cache.keys())


# Global workflow loader instance
workflow_loader = WorkflowLoader()
