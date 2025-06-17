#!/usr/bin/env python3
"""
Agent discovery and loading functionality
"""

import importlib.util
from pathlib import Path
from typing import List, Dict, Any, Optional

# Import after checking if available
try:
    from signalwire_agents.core.agent_base import AgentBase
    AGENT_BASE_AVAILABLE = True
except ImportError:
    AgentBase = None
    AGENT_BASE_AVAILABLE = False


def discover_agents_in_file(agent_path: str) -> List[Dict[str, Any]]:
    """
    Discover all available agents in a Python file without instantiating them
    
    Args:
        agent_path: Path to the Python file containing agents
        
    Returns:
        List of dictionaries with agent information
        
    Raises:
        ImportError: If the file cannot be imported
        FileNotFoundError: If the file doesn't exist
    """
    if not AGENT_BASE_AVAILABLE:
        raise ImportError("AgentBase not available. Please install signalwire-agents package.")
    
    agent_path = Path(agent_path).resolve()
    
    if not agent_path.exists():
        raise FileNotFoundError(f"Agent file not found: {agent_path}")
    
    if not agent_path.suffix == '.py':
        raise ValueError(f"Agent file must be a Python file (.py): {agent_path}")
    
    # Load the module, but prevent main() execution by setting __name__ to something other than "__main__"
    spec = importlib.util.spec_from_file_location("agent_module", agent_path)
    module = importlib.util.module_from_spec(spec)
    
    try:
        # Set __name__ to prevent if __name__ == "__main__": blocks from running
        module.__name__ = "agent_module"
        spec.loader.exec_module(module)
    except Exception as e:
        raise ImportError(f"Failed to load agent module: {e}")
    
    agents_found = []
    
    # Look for AgentBase instances
    for name, obj in vars(module).items():
        if isinstance(obj, AgentBase):
            agents_found.append({
                'name': name,
                'class_name': obj.__class__.__name__,
                'type': 'instance',
                'agent_name': getattr(obj, 'name', 'Unknown'),
                'route': getattr(obj, 'route', 'Unknown'),
                'description': obj.__class__.__doc__,
                'object': obj
            })
    
    # Look for AgentBase subclasses (that could be instantiated)
    for name, obj in vars(module).items():
        if (isinstance(obj, type) and 
            issubclass(obj, AgentBase) and 
            obj != AgentBase):
            # Check if we already found an instance of this class
            instance_found = any(agent['class_name'] == name for agent in agents_found)
            if not instance_found:
                try:
                    # Try to get class information without instantiating
                    agent_info = {
                        'name': name,
                        'class_name': name,
                        'type': 'class',
                        'agent_name': 'Unknown (not instantiated)',
                        'route': 'Unknown (not instantiated)',
                        'description': obj.__doc__,
                        'object': obj
                    }
                    agents_found.append(agent_info)
                except Exception:
                    # If we can't get info, still record that the class exists
                    agents_found.append({
                        'name': name,
                        'class_name': name,
                        'type': 'class',
                        'agent_name': 'Unknown (not instantiated)',
                        'route': 'Unknown (not instantiated)',
                        'description': obj.__doc__ or 'No description available',
                        'object': obj
                    })
    
    return agents_found


def load_agent_from_file(agent_path: str, agent_class_name: Optional[str] = None) -> 'AgentBase':
    """
    Load an agent from a Python file
    
    Args:
        agent_path: Path to the Python file containing the agent
        agent_class_name: Optional name of the agent class to instantiate
        
    Returns:
        AgentBase instance
        
    Raises:
        ImportError: If the file cannot be imported
        ValueError: If no agent is found in the file
    """
    if not AGENT_BASE_AVAILABLE:
        raise ImportError("AgentBase not available. Please install signalwire-agents package.")
    
    agent_path = Path(agent_path).resolve()
    
    if not agent_path.exists():
        raise FileNotFoundError(f"Agent file not found: {agent_path}")
    
    if not agent_path.suffix == '.py':
        raise ValueError(f"Agent file must be a Python file (.py): {agent_path}")
    
    # Load the module, but prevent main() execution by setting __name__ to something other than "__main__"
    spec = importlib.util.spec_from_file_location("agent_module", agent_path)
    module = importlib.util.module_from_spec(spec)
    
    try:
        # Set __name__ to prevent if __name__ == "__main__": blocks from running
        module.__name__ = "agent_module"
        spec.loader.exec_module(module)
    except Exception as e:
        raise ImportError(f"Failed to load agent module: {e}")
    
    # Find the agent instance
    agent = None
    
    # If agent_class_name is specified, try to instantiate that specific class first
    if agent_class_name:
        if hasattr(module, agent_class_name):
            obj = getattr(module, agent_class_name)
            if isinstance(obj, type) and issubclass(obj, AgentBase) and obj != AgentBase:
                try:
                    agent = obj()
                    if agent and not agent.route.endswith('dummy'):  # Avoid test agents with dummy routes
                        pass  # Successfully created specific agent
                    else:
                        agent = obj()  # Create anyway if requested specifically
                except Exception as e:
                    raise ValueError(f"Failed to instantiate agent class '{agent_class_name}': {e}")
            else:
                raise ValueError(f"'{agent_class_name}' is not a valid AgentBase subclass")
        else:
            raise ValueError(f"Agent class '{agent_class_name}' not found in {agent_path}")
    
    # Strategy 1: Look for 'agent' variable (most common pattern)
    if agent is None and hasattr(module, 'agent') and isinstance(module.agent, AgentBase):
        agent = module.agent
    
    # Strategy 2: Look for any AgentBase instance in module globals
    if agent is None:
        agents_found = []
        for name, obj in vars(module).items():
            if isinstance(obj, AgentBase):
                agents_found.append((name, obj))
        
        if len(agents_found) == 1:
            agent = agents_found[0][1]
        elif len(agents_found) > 1:
            # Multiple agents found, prefer one named 'agent'
            for name, obj in agents_found:
                if name == 'agent':
                    agent = obj
                    break
            # If no 'agent' variable, use the first one
            if agent is None:
                agent = agents_found[0][1]
                print(f"Warning: Multiple agents found, using '{agents_found[0][0]}'")
                print(f"Hint: Use --agent-class parameter to choose specific agent")
    
    # Strategy 3: Look for AgentBase subclass and try to instantiate it
    if agent is None:
        agent_classes_found = []
        for name, obj in vars(module).items():
            if (isinstance(obj, type) and 
                issubclass(obj, AgentBase) and 
                obj != AgentBase):
                agent_classes_found.append((name, obj))
        
        if len(agent_classes_found) == 1:
            try:
                agent = agent_classes_found[0][1]()
            except Exception as e:
                print(f"Warning: Failed to instantiate {agent_classes_found[0][0]}: {e}")
        elif len(agent_classes_found) > 1:
            # Multiple agent classes found
            class_names = [name for name, _ in agent_classes_found]
            raise ValueError(f"Multiple agent classes found: {', '.join(class_names)}. "
                           f"Please specify which agent class to use with --agent-class parameter. "
                           f"Usage: swaig-test {agent_path} [tool_name] [args] --agent-class <AgentClassName>")
        else:
            # Try instantiating any AgentBase class we can find
            for name, obj in vars(module).items():
                if (isinstance(obj, type) and 
                    issubclass(obj, AgentBase) and 
                    obj != AgentBase):
                    try:
                        agent = obj()
                        break
                    except Exception as e:
                        print(f"Warning: Failed to instantiate {name}: {e}")
    
    # Strategy 4: Try calling a modified main() function that doesn't start the server
    if agent is None and hasattr(module, 'main'):
        print("Warning: No agent instance found, attempting to call main() without server startup")
        try:
            # Temporarily patch AgentBase.serve to prevent server startup
            original_serve = AgentBase.serve
            captured_agent = []
            
            def mock_serve(self, *args, **kwargs):
                captured_agent.append(self)
                print(f"  (Intercepted serve() call, agent captured for testing)")
                return self
            
            AgentBase.serve = mock_serve
            
            try:
                result = module.main()
                if isinstance(result, AgentBase):
                    agent = result
                elif captured_agent:
                    agent = captured_agent[0]
            finally:
                # Restore original serve method
                AgentBase.serve = original_serve
                
        except Exception as e:
            print(f"Warning: Failed to call main() function: {e}")
    
    if agent is None:
        raise ValueError(f"No agent found in {agent_path}. The file must contain either:\n"
                        f"- An AgentBase instance (e.g., agent = MyAgent())\n"
                        f"- An AgentBase subclass that can be instantiated\n"
                        f"- A main() function that creates and returns an agent")
    
    return agent