"""
Project Manager - Handles multi-project configuration for Feedback Collector.

Each project has its own:
- Taxonomy (categories, keywords, impact types)
- Target database (Fabric SQL connection)
- Community channels / data sources
- Collection settings

Projects are stored in src/projects/<project_id>/ with:
- project.json   - Project metadata, DB config, source config
- categories.json - Feedback categories taxonomy
- keywords.json   - Search keywords
- impact_types.json - Impact type definitions
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

PROJECTS_DIR = os.path.join(os.path.dirname(__file__), 'projects')


def get_projects_dir():
    """Get the projects directory path, creating it if needed."""
    if not os.path.exists(PROJECTS_DIR):
        os.makedirs(PROJECTS_DIR)
    return PROJECTS_DIR


def list_projects() -> List[Dict[str, Any]]:
    """List all available project profiles.
    
    Returns a list of project summary dicts with id, name, description, icon, color.
    """
    projects = []
    projects_dir = get_projects_dir()
    
    if not os.path.exists(projects_dir):
        return projects
    
    for entry in sorted(os.listdir(projects_dir)):
        project_path = os.path.join(projects_dir, entry)
        project_file = os.path.join(project_path, 'project.json')
        
        if os.path.isdir(project_path) and os.path.exists(project_file):
            try:
                with open(project_file, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)
                
                projects.append({
                    'id': project_data.get('id', entry),
                    'name': project_data.get('name', entry),
                    'description': project_data.get('description', ''),
                    'icon': project_data.get('icon', 'bi-folder'),
                    'color': project_data.get('color', '#0078d4'),
                })
            except Exception as e:
                logger.error(f"Error loading project {entry}: {e}")
                continue
    
    return projects


def load_project(project_id: str) -> Dict[str, Any]:
    """Load a full project profile including all configuration.
    
    Returns dict with keys: project, categories, keywords, impact_types
    """
    project_dir = os.path.join(get_projects_dir(), project_id)
    
    if not os.path.exists(project_dir):
        raise FileNotFoundError(f"Project '{project_id}' not found at {project_dir}")
    
    # Load project.json
    project_file = os.path.join(project_dir, 'project.json')
    with open(project_file, 'r', encoding='utf-8') as f:
        project_data = json.load(f)
    
    # Load categories
    categories = _load_json_file(os.path.join(project_dir, 'categories.json'), {})
    
    # Load keywords
    keywords = _load_json_file(os.path.join(project_dir, 'keywords.json'), [])
    
    # Load impact types
    impact_types = _load_json_file(os.path.join(project_dir, 'impact_types.json'), {})
    
    # Load audience config (optional per-project audience detection)
    audience_config = _load_json_file(os.path.join(project_dir, 'audience_config.json'), None)
    
    return {
        'project': project_data,
        'categories': categories,
        'keywords': keywords,
        'impact_types': impact_types,
        'audience_config': audience_config
    }


def save_project(project_id: str, project_data: Dict[str, Any]) -> None:
    """Save project metadata (project.json)."""
    project_dir = os.path.join(get_projects_dir(), project_id)
    os.makedirs(project_dir, exist_ok=True)
    
    project_file = os.path.join(project_dir, 'project.json')
    with open(project_file, 'w', encoding='utf-8') as f:
        json.dump(project_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved project metadata: {project_id}")


def save_project_categories(project_id: str, categories: Dict) -> None:
    """Save categories for a specific project."""
    project_dir = os.path.join(get_projects_dir(), project_id)
    os.makedirs(project_dir, exist_ok=True)
    
    filepath = os.path.join(project_dir, 'categories.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(categories, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved categories for project: {project_id}")


def save_project_keywords(project_id: str, keywords: List[str]) -> None:
    """Save keywords for a specific project."""
    project_dir = os.path.join(get_projects_dir(), project_id)
    os.makedirs(project_dir, exist_ok=True)
    
    filepath = os.path.join(project_dir, 'keywords.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(keywords, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved keywords for project: {project_id}")


def save_project_impact_types(project_id: str, impact_types: Dict) -> None:
    """Save impact types for a specific project."""
    project_dir = os.path.join(get_projects_dir(), project_id)
    os.makedirs(project_dir, exist_ok=True)
    
    filepath = os.path.join(project_dir, 'impact_types.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(impact_types, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved impact types for project: {project_id}")


def get_project_db_config(project_id: str) -> Dict[str, str]:
    """Get database configuration for a specific project.
    
    Returns dict with: server, database_name, authentication, connection_string (if set)
    """
    project_dir = os.path.join(get_projects_dir(), project_id)
    project_file = os.path.join(project_dir, 'project.json')
    
    with open(project_file, 'r', encoding='utf-8') as f:
        project_data = json.load(f)
    
    db_config = project_data.get('database', {})
    
    result = {
        'authentication': db_config.get('authentication', 'ActiveDirectoryInteractive')
    }
    
    # Check for direct connection string first
    if db_config.get('connection_string'):
        result['connection_string'] = db_config['connection_string']
    
    # Check for direct server/database values
    if db_config.get('server'):
        result['server'] = db_config['server']
    elif db_config.get('server_env'):
        result['server'] = os.getenv(db_config['server_env'], '')
    
    if db_config.get('database_name'):
        result['database_name'] = db_config['database_name']
    elif db_config.get('database_env'):
        result['database_name'] = os.getenv(db_config['database_env'], '')
    
    return result


def get_project_sources(project_id: str) -> Dict[str, Any]:
    """Get source configuration for a specific project."""
    project_dir = os.path.join(get_projects_dir(), project_id)
    project_file = os.path.join(project_dir, 'project.json')
    
    with open(project_file, 'r', encoding='utf-8') as f:
        project_data = json.load(f)
    
    return project_data.get('sources', {})


def update_project_sources(project_id: str, sources: Dict[str, Any]) -> None:
    """Update source configuration for a specific project."""
    project_dir = os.path.join(get_projects_dir(), project_id)
    project_file = os.path.join(project_dir, 'project.json')
    
    with open(project_file, 'r', encoding='utf-8') as f:
        project_data = json.load(f)
    
    project_data['sources'] = sources
    
    with open(project_file, 'w', encoding='utf-8') as f:
        json.dump(project_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Updated sources for project: {project_id}")


def update_project_settings(project_id: str, settings: Dict[str, Any]) -> None:
    """Update collection settings for a specific project."""
    project_dir = os.path.join(get_projects_dir(), project_id)
    project_file = os.path.join(project_dir, 'project.json')
    
    with open(project_file, 'r', encoding='utf-8') as f:
        project_data = json.load(f)
    
    project_data['settings'] = settings
    
    with open(project_file, 'w', encoding='utf-8') as f:
        json.dump(project_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Updated settings for project: {project_id}")


def create_project(project_id: str, name: str, description: str = '',
                   icon: str = 'bi-folder', color: str = '#0078d4',
                   db_server: str = '', db_name: str = '',
                   db_auth: str = 'ActiveDirectoryInteractive',
                   db_connection_string: str = '') -> Dict[str, Any]:
    """Create a new project profile with default configuration."""
    project_dir = os.path.join(get_projects_dir(), project_id)
    
    if os.path.exists(project_dir):
        raise FileExistsError(f"Project '{project_id}' already exists")
    
    os.makedirs(project_dir)
    
    project_data = {
        'id': project_id,
        'name': name,
        'description': description,
        'icon': icon,
        'color': color,
        'database': {
            'server': db_server,
            'database_name': db_name,
            'authentication': db_auth,
        },
        'sources': {
            'reddit': {'enabled': True, 'subreddit': 'MicrosoftFabric', 'sort': 'new', 'timeFilter': 'month', 'maxItems': 5},
            'github': {'enabled': False, 'repositories': [], 'state': 'all', 'maxItems': 5},
            'githubIssues': {'enabled': False, 'repositories': [], 'state': 'all', 'maxItems': 5},
            'fabricCommunity': {'enabled': True, 'forums': [], 'maxItems': 5},
            'ado': {'enabled': False, 'parentWorkItem': '', 'maxItems': 5}
        },
        'settings': {
            'timeRangeMonths': 6,
            'maxItemsPerSource': 5,
            'respectRateLimits': True,
            'duplicateDetection': True
        }
    }
    
    if db_connection_string:
        project_data['database']['connection_string'] = db_connection_string
    
    # Save project.json
    save_project(project_id, project_data)
    
    # Create empty taxonomy files
    save_project_keywords(project_id, [])
    save_project_categories(project_id, {})
    save_project_impact_types(project_id, {})
    
    logger.info(f"Created new project: {project_id} ({name})")
    return project_data


def delete_project(project_id: str) -> bool:
    """Delete a project profile."""
    import shutil
    project_dir = os.path.join(get_projects_dir(), project_id)
    
    if not os.path.exists(project_dir):
        return False
    
    shutil.rmtree(project_dir)
    logger.info(f"Deleted project: {project_id}")
    return True


def _load_json_file(filepath: str, default: Any) -> Any:
    """Load a JSON file with fallback to default."""
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                return default
            return json.loads(content)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Error loading {filepath}: {e}")
        return default
