from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, Dict, Any, List
import httpx
import json
from pydantic import BaseModel
from core.database import get_db
from sqlalchemy.orm import Session
from models.models import Model
from models.user import User
from models.keys import Key
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict, Annotated

router = APIRouter()

class AgenticQuery(BaseModel):
    model_api_key: str
    user_prompt: str
    conversation_history: Optional[List[Dict[str, str]]] = []

class AgenticResponse(BaseModel):
    response: str
    agent_used: str
    tools_used: List[str]
    reasoning: str

# Agent State
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_data: Dict[str, Any]
    current_agent: str
    tools_used: List[str]
    reasoning: str

def get_current_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from API key in header"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    # Check if key exists and is not expired
    key_record = db.query(Key).filter(
        Key.key == x_api_key,
        Key.expires_at > datetime.utcnow()
    ).first()
    
    if not key_record:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    
    return key_record.owner_user

# Enhanced Tool definitions
def get_comprehensive_activity_data(user_data: Dict[str, Any]) -> str:
    """Get comprehensive activity data with detailed analysis"""
    activities = user_data.get('activities', [])
    
    if not activities:
        return "No activity data available."
    
    # Group activities by task and activity name
    task_activities = {}
    total_time = 0
    completed_activities = 0
    
    for activity in activities:
        duration = activity.get('duration', 0)
        total_time += duration
        if activity.get('status') == 'DONE':
            completed_activities += 1
        
        # Group by task title if available, otherwise by activity name
        task_title = activity.get('task_title')
        activity_name = activity.get('name', 'Unnamed Activity')
        
        # Create a meaningful key for grouping
        if task_title:
            group_key = f"{task_title}"
        else:
            group_key = activity_name
        
        if group_key not in task_activities:
            task_activities[group_key] = {
                'total_time': 0, 
                'sessions': 0, 
                'status': activity.get('status', 'UNKNOWN'),
                'task_title': task_title,
                'activity_name': activity_name
            }
        task_activities[group_key]['total_time'] += duration
        task_activities[group_key]['sessions'] += 1
    
    # Sort by total time
    sorted_activities = sorted(task_activities.items(), key=lambda x: x[1]['total_time'], reverse=True)
    
    result = f"**COMPREHENSIVE ACTIVITY ANALYSIS:**\n"
    result += f"- Total tracked time: {total_time} minutes ({total_time/60:.1f} hours)\n"
    result += f"- Total activities: {len(activities)}\n"
    result += f"- Completed activities: {completed_activities}\n"
    result += f"- Unique task/activity types: {len(task_activities)}\n\n"
    
    result += "**TOP ACTIVITIES BY TIME:**\n"
    for group_key, data in sorted_activities[:10]:  # Top 10
        avg_duration = data['total_time'] / data['sessions'] if data['sessions'] > 0 else 0
        status_icon = "✅" if data['status'] == 'DONE' else "🔄" if data['status'] == 'DOING' else "📋"
        result += f"- {group_key}: {data['total_time']} min total ({data['sessions']} sessions, avg {avg_duration:.1f} min) {status_icon}\n"
    
    return result

def get_task_priorities(user_data: Dict[str, Any]) -> str:
    """Get comprehensive task priorities and status analysis"""
    tasks = user_data.get('tasks', [])
    
    if not tasks:
        return "No tasks found."
    
    # Categorize tasks
    urgent_tasks = [t for t in tasks if t.get('is_urgent') and t.get('state') not in ['done', 'deleted']]
    important_tasks = [t for t in tasks if t.get('is_important') and t.get('state') not in ['done', 'deleted']]
    todo_tasks = [t for t in tasks if t.get('state') == 'todo']
    doing_tasks = [t for t in tasks if t.get('state') == 'doing']
    done_tasks = [t for t in tasks if t.get('state') == 'done']
    open_tasks = [t for t in tasks if t.get('state') == 'open']
    
    result = f"**TASK STATUS OVERVIEW:**\n"
    result += f"- Total tasks: {len(tasks)}\n"
    result += f"- Todo: {len(todo_tasks)}\n"
    result += f"- In Progress: {len(doing_tasks)}\n"
    result += f"- Completed: {len(done_tasks)}\n"
    result += f"- Open: {len(open_tasks)}\n\n"
    
    result += f"**URGENT TASKS ({len(urgent_tasks)}):**\n"
    for task in urgent_tasks[:5]:
        result += f"- {task['title']} (Priority: {'High' if task.get('is_important') else 'Urgent'})\n"
    
    result += f"\n**IMPORTANT TASKS ({len(important_tasks)}):**\n"
    for task in important_tasks[:5]:
        result += f"- {task['title']} (State: {task.get('state', 'unknown')})\n"
    
    # Get upcoming deadlines
    upcoming = [t for t in tasks if t.get('deadline') and t.get('state') not in ['done', 'deleted']]
    upcoming.sort(key=lambda x: x.get('deadline', ''))
    if upcoming:
        result += f"\n**UPCOMING DEADLINES:**\n"
        for task in upcoming[:5]:
            result += f"- {task['title']} - {task['deadline']}\n"
    
    return result

def analyze_productivity_metrics(user_data: Dict[str, Any]) -> str:
    """Analyze comprehensive productivity metrics from activities and tasks"""
    activities = user_data.get('activities', [])
    tasks = user_data.get('tasks', [])
    projects = user_data.get('projects', [])
    
    # Calculate time metrics
    total_time = sum(activity.get('duration', 0) for activity in activities)
    completed_activities = len([a for a in activities if a.get('status') == 'DONE'])
    avg_session = (total_time / len(activities)) if activities else 0
    
    # Task metrics
    completed_tasks = len([t for t in tasks if t.get('state') == 'done'])
    active_tasks = len([t for t in tasks if t.get('state') in ['todo', 'doing', 'open']])
    completion_rate = (completed_tasks / len(tasks) * 100) if tasks else 0
    
    # Project metrics
    active_projects = len(projects)
    
    # Time distribution analysis
    recent_activities = [a for a in activities if a.get('duration', 0) > 0]
    if recent_activities:
        avg_daily_time = total_time / 30  # Assuming 30 days of data
        most_productive_activity = max(recent_activities, key=lambda x: x.get('duration', 0))
    else:
        avg_daily_time = 0
        most_productive_activity = None
    
    result = f"**COMPREHENSIVE PRODUCTIVITY METRICS:**\n"
    result += f"- Total tracked time: {total_time} minutes ({total_time/60:.1f} hours)\n"
    result += f"- Average session duration: {avg_session:.1f} minutes\n"
    result += f"- Completed activities: {completed_activities}/{len(activities)} ({completed_activities/len(activities)*100:.1f}%)\n"
    result += f"- Task completion rate: {completion_rate:.1f}% ({completed_tasks}/{len(tasks)} tasks)\n"
    result += f"- Active tasks: {active_tasks}\n"
    result += f"- Active projects: {active_projects}\n"
    result += f"- Average daily time: {avg_daily_time:.1f} minutes\n"
    
    if most_productive_activity:
        result += f"- Most time spent on: {most_productive_activity.get('name', 'Unknown')} ({most_productive_activity.get('duration', 0)} min)\n"
    
    return result

def get_time_analysis(user_data: Dict[str, Any]) -> str:
    """Get detailed time analysis and patterns"""
    activities = user_data.get('activities', [])
    
    if not activities:
        return "No activity data for time analysis."
    
    # Group by day of week and hour
    daily_totals = {}
    hourly_totals = {}
    
    for activity in activities:
        if activity.get('created_at'):
            try:
                # Parse the datetime
                dt = datetime.fromisoformat(activity['created_at'].replace('Z', '+00:00'))
                day_name = dt.strftime('%A')
                hour = dt.hour
                
                duration = activity.get('duration', 0)
                
                daily_totals[day_name] = daily_totals.get(day_name, 0) + duration
                hourly_totals[hour] = hourly_totals.get(hour, 0) + duration
            except:
                continue
    
    result = "**TIME PATTERN ANALYSIS:**\n"
    
    if daily_totals:
        result += "\n**MOST PRODUCTIVE DAYS:**\n"
        sorted_days = sorted(daily_totals.items(), key=lambda x: x[1], reverse=True)
        for day, time in sorted_days[:3]:
            result += f"- {day}: {time} minutes ({time/60:.1f} hours)\n"
    
    if hourly_totals:
        result += "\n**MOST PRODUCTIVE HOURS:**\n"
        sorted_hours = sorted(hourly_totals.items(), key=lambda x: x[1], reverse=True)
        for hour, time in sorted_hours[:5]:
            result += f"- {hour:02d}:00: {time} minutes\n"
    
    return result

def get_project_performance(user_data: Dict[str, Any]) -> str:
    """Analyze project performance and progress"""
    projects = user_data.get('projects', [])
    tasks = user_data.get('tasks', [])
    activities = user_data.get('activities', [])
    
    if not projects:
        return "No projects found."
    
    result = "**PROJECT PERFORMANCE ANALYSIS:**\n"
    
    for project in projects:
        project_id = project.get('id')
        project_name = project.get('name', 'Unnamed Project')
        
        # Get tasks for this project
        project_tasks = [t for t in tasks if t.get('proj_id') == project_id]
        completed_tasks = [t for t in project_tasks if t.get('state') == 'done']
        
        # Get activities related to this project (through tasks)
        project_activities = []
        for task in project_tasks:
            task_activities = [a for a in activities if a.get('task_id') == task.get('id')]
            project_activities.extend(task_activities)
        
        total_time = sum(a.get('duration', 0) for a in project_activities)
        completion_rate = (len(completed_tasks) / len(project_tasks) * 100) if project_tasks else 0
        
        result += f"\n**{project_name}:**\n"
        result += f"- Tasks: {len(completed_tasks)}/{len(project_tasks)} completed ({completion_rate:.1f}%)\n"
        result += f"- Time invested: {total_time} minutes ({total_time/60:.1f} hours)\n"
        result += f"- Activity sessions: {len(project_activities)}\n"
    
    return result

def get_project_overview(user_data: Dict[str, Any]) -> str:
    """Get comprehensive project overview and status"""
    projects = user_data.get('projects', [])
    tasks = user_data.get('tasks', [])
    activities = user_data.get('activities', [])
    
    if not projects:
        return "No projects found."
    
    result = "**COMPREHENSIVE PROJECT OVERVIEW:**\n"
    
    for project in projects:
        project_id = project.get('id')
        project_name = project.get('name', 'Unnamed Project')
        project_color = project.get('color', '#000000')
        
        # Get project tasks
        project_tasks = [t for t in tasks if t.get('proj_id') == project_id]
        completed_tasks = [t for t in project_tasks if t.get('state') == 'done']
        active_tasks = [t for t in project_tasks if t.get('state') in ['todo', 'doing', 'open']]
        
        # Get project activities
        project_activities = []
        for task in project_tasks:
            task_activities = [a for a in activities if a.get('task_id') == task.get('id')]
            project_activities.extend(task_activities)
        
        total_time = sum(a.get('duration', 0) for a in project_activities)
        completion_rate = (len(completed_tasks) / len(project_tasks) * 100) if project_tasks else 0
        
        result += f"\n**{project_name}** (Color: {project_color}):\n"
        result += f"- Tasks: {len(completed_tasks)}/{len(project_tasks)} completed ({completion_rate:.1f}%)\n"
        result += f"- Active tasks: {len(active_tasks)}\n"
        result += f"- Time invested: {total_time} minutes ({total_time/60:.1f} hours)\n"
        result += f"- Activity sessions: {len(project_activities)}\n"
        
        # Show recent activity
        if project_activities:
            recent_activity = max(project_activities, key=lambda x: x.get('created_at', ''))
            result += f"- Last activity: {recent_activity.get('name', 'Unknown')} ({recent_activity.get('duration', 0)} min)\n"
    
    return result

def get_recent_activities(user_data: Dict[str, Any]) -> str:
    """Get recent activities for context"""
    activities = user_data.get('activities', [])
    
    if not activities:
        return "No recent activities found."
    
    # Sort by date (most recent first) and take top 10
    sorted_activities = sorted(activities, key=lambda x: x.get('created_at', ''), reverse=True)[:10]
    
    overview = "**RECENT ACTIVITIES:**\n"
    for activity in sorted_activities:
        name = activity.get('name', 'Unnamed Activity')
        duration = activity.get('duration', 0)
        created_at = activity.get('created_at', 'Unknown date')
        overview += f"- {name} ({duration} minutes) - {created_at}\n"
    
    if len(activities) > 10:
        overview += f"... and {len(activities) - 10} more activities\n"
    
    return overview

def get_task_details(user_data: Dict[str, Any]) -> str:
    """Get detailed task information"""
    tasks = user_data.get('tasks', [])
    
    if not tasks:
        return "No tasks found."
    
    # Categorize tasks by state
    todo_tasks = [t for t in tasks if t.get('state') == 'todo']
    doing_tasks = [t for t in tasks if t.get('state') == 'doing']
    done_tasks = [t for t in tasks if t.get('state') == 'done']
    
    overview = "**TASK BREAKDOWN:**\n"
    overview += f"- Todo: {len(todo_tasks)} tasks\n"
    overview += f"- In Progress: {len(doing_tasks)} tasks\n"
    overview += f"- Completed: {len(done_tasks)} tasks\n"
    
    if todo_tasks:
        overview += "\n**TODO TASKS:**\n"
        for task in todo_tasks[:5]:  # Show top 5
            name = task.get('name', 'Unnamed Task')
            priority = "High" if task.get('is_urgent') and task.get('is_important') else "Normal"
            overview += f"- {name} (Priority: {priority})\n"
    
    if doing_tasks:
        overview += "\n**IN PROGRESS TASKS:**\n"
        for task in doing_tasks[:3]:  # Show top 3
            name = task.get('name', 'Unnamed Task')
            overview += f"- {name}\n"
    
    return overview

def get_activity_analysis(user_data: Dict[str, Any]) -> str:
    """Get activity analysis and patterns"""
    activities = user_data.get('activities', [])
    
    if not activities:
        return "No activity data available for analysis."
    
    # Calculate total time
    total_time = sum(activity.get('duration', 0) for activity in activities)
    
    # Group by activity name
    activity_groups = {}
    for activity in activities:
        name = activity.get('name', 'Unnamed Activity')
        duration = activity.get('duration', 0)
        if name in activity_groups:
            activity_groups[name]['total_duration'] += duration
            activity_groups[name]['count'] += 1
        else:
            activity_groups[name] = {'total_duration': duration, 'count': 1}
    
    # Sort by total duration
    sorted_activities = sorted(activity_groups.items(), key=lambda x: x[1]['total_duration'], reverse=True)
    
    overview = f"**ACTIVITY ANALYSIS:**\n"
    overview += f"- Total tracked time: {total_time} minutes ({total_time/60:.1f} hours)\n"
    overview += f"- Total activities: {len(activities)}\n"
    overview += f"- Unique activity types: {len(activity_groups)}\n\n"
    
    overview += "**TOP ACTIVITIES BY TIME:**\n"
    for name, data in sorted_activities[:5]:  # Top 5
        avg_duration = data['total_duration'] / data['count']
        overview += f"- {name}: {data['total_duration']} min total ({data['count']} sessions, avg {avg_duration:.1f} min)\n"
    
    return overview

def get_learning_analysis(user_data: Dict[str, Any]) -> str:
    """Analyze learning activities and progress"""
    activities = user_data.get('activities', [])
    tasks = user_data.get('tasks', [])
    projects = user_data.get('projects', [])
    
    # Find learning-related projects
    learning_projects = [p for p in projects if any(keyword in p.get('name', '').lower() for keyword in ['learn', 'study', 'course', 'german', 'french', 'language'])]
    
    result = "**LEARNING ANALYSIS:**\n"
    
    if learning_projects:
        result += f"Found {len(learning_projects)} learning projects:\n"
        for project in learning_projects:
            project_id = project.get('id')
            project_name = project.get('name')
            
            # Get tasks for this learning project
            project_tasks = [t for t in tasks if t.get('proj_id') == project_id]
            completed_tasks = [t for t in project_tasks if t.get('state') == 'done']
            
            # Get activities for this project
            project_activities = []
            for task in project_tasks:
                task_activities = [a for a in activities if a.get('task_id') == task.get('id')]
                project_activities.extend(task_activities)
            
            total_time = sum(a.get('duration', 0) for a in project_activities)
            
            result += f"\n**{project_name}:**\n"
            result += f"- Tasks completed: {len(completed_tasks)}/{len(project_tasks)}\n"
            result += f"- Time spent: {total_time} minutes ({total_time/60:.1f} hours)\n"
            result += f"- Study sessions: {len(project_activities)}\n"
            
            if project_activities:
                avg_session = total_time / len(project_activities)
                result += f"- Average session: {avg_session:.1f} minutes\n"
    else:
        result += "No learning projects identified.\n"
    
    # Analyze all learning-related activities
    learning_activities = [a for a in activities if any(keyword in a.get('name', '').lower() for keyword in ['learn', 'study', 'german', 'french', 'language', 'course'])]
    
    if learning_activities:
        total_learning_time = sum(a.get('duration', 0) for a in learning_activities)
        result += f"\n**OVERALL LEARNING TIME:**\n"
        result += f"- Total learning time: {total_learning_time} minutes ({total_learning_time/60:.1f} hours)\n"
        result += f"- Learning sessions: {len(learning_activities)}\n"
        result += f"- Average learning session: {total_learning_time/len(learning_activities):.1f} minutes\n"
    
    return result

def get_productivity_insights(user_data: Dict[str, Any]) -> str:
    """Get deep productivity insights and recommendations"""
    activities = user_data.get('activities', [])
    tasks = user_data.get('tasks', [])
    projects = user_data.get('projects', [])
    
    result = "**PRODUCTIVITY INSIGHTS & RECOMMENDATIONS:**\n"
    
    # Time analysis
    total_time = sum(a.get('duration', 0) for a in activities)
    if total_time > 0:
        avg_daily = total_time / 30  # Assuming 30 days
        result += f"\n**TIME MANAGEMENT:**\n"
        result += f"- Daily average: {avg_daily:.1f} minutes\n"
        result += f"- Weekly average: {avg_daily * 7:.1f} minutes\n"
        
        if avg_daily < 60:
            result += "- ⚠️ Low daily activity - consider increasing focus time\n"
        elif avg_daily > 300:
            result += "- ⚠️ High daily activity - ensure work-life balance\n"
        else:
            result += "- ✅ Good daily activity level\n"
    
    # Task completion analysis
    completed_tasks = len([t for t in tasks if t.get('state') == 'done'])
    total_tasks = len(tasks)
    if total_tasks > 0:
        completion_rate = (completed_tasks / total_tasks) * 100
        result += f"\n**TASK COMPLETION:**\n"
        result += f"- Completion rate: {completion_rate:.1f}%\n"
        
        if completion_rate < 30:
            result += "- ⚠️ Low completion rate - consider breaking down large tasks\n"
        elif completion_rate > 80:
            result += "- ✅ Excellent completion rate\n"
        else:
            result += "- 📈 Good completion rate, room for improvement\n"
    
    # Project progress
    active_projects = len(projects)
    if active_projects > 5:
        result += f"\n**PROJECT MANAGEMENT:**\n"
        result += f"- ⚠️ Many active projects ({active_projects}) - consider focusing on fewer projects\n"
    elif active_projects > 0:
        result += f"\n**PROJECT MANAGEMENT:**\n"
        result += f"- ✅ Good project count ({active_projects})\n"
    
    return result

def create_schedule(user_data: Dict[str, Any], schedule_type: str = "daily") -> str:
    """Create a schedule based on tasks and priorities"""
    tasks = user_data.get('tasks', [])
    urgent_tasks = [t for t in tasks if t.get('is_urgent') and t.get('state') != 'done']
    important_tasks = [t for t in tasks if t.get('is_important') and t.get('state') != 'done']
    
    if schedule_type == "daily":
        schedule = "DAILY SCHEDULE:\n"
        schedule += "9:00-12:00: Focus on urgent tasks\n"
        schedule += "12:00-13:00: Lunch break\n"
        schedule += "13:00-16:00: Important tasks\n"
        schedule += "16:00-17:00: Review and planning\n"
    else:
        schedule = "WEEKLY SCHEDULE:\n"
        schedule += "Monday-Friday: Deep work blocks\n"
        schedule += "Weekend: Review and planning\n"
    
    return schedule

# Tool functions are defined above and used directly in agent nodes

# Agent nodes
def planning_agent(state: AgentState) -> AgentState:
    """Planning agent specialized in task prioritization and scheduling"""
    messages = state["messages"]
    user_data = state["user_data"]

    # Get comprehensive data using enhanced tools
    priorities = get_task_priorities(user_data)
    project_overview = get_project_overview(user_data)
    task_details = get_task_details(user_data)
    activities = get_comprehensive_activity_data(user_data)
    learning_analysis = get_learning_analysis(user_data)
    productivity_insights = get_productivity_insights(user_data)
    time_analysis = get_time_analysis(user_data)
    
    # Create a comprehensive system prompt for planning
    system_prompt = f"""You are a Planning Agent specialized in task prioritization, scheduling, and project planning.

CURRENT CONTEXT:
- Projects: {len(user_data.get('projects', []))} active
- Tasks: {len(user_data.get('tasks', []))} total
- Activities: {len(user_data.get('activities', []))} tracked
- Reminders: {len(user_data.get('reminders', []))} set

CURRENT DATA:
{priorities}

{project_overview}

{task_details}

{activities}

{learning_analysis}

{productivity_insights}

{time_analysis}

YOUR EXPERTISE:
- Task prioritization using Eisenhower Matrix (urgent/important)
- Time blocking and scheduling optimization
- Project milestone planning and deadline management
- Resource allocation and capacity planning
- Workflow optimization and productivity enhancement

INSTRUCTIONS:
- Analyze the current task landscape and provide actionable planning advice
- Create specific, time-bound schedules when requested
- Prioritize tasks based on urgency, importance, and deadlines
- Suggest time management strategies and productivity techniques
- Consider dependencies between tasks and projects
- Provide clear, step-by-step planning guidance
- Use bullet points and structured formats for clarity
- Focus on practical, implementable solutions

RESPONSE STYLE:
- Be specific and actionable
- Provide concrete time estimates when possible
- Use planning terminology (deadlines, milestones, priorities)
- Include checklists and structured plans
- Ask clarifying questions about constraints or preferences"""

    # Add system message
    messages.append(SystemMessage(content=system_prompt))
    
    # Create response based on user input
    user_input = messages[-1].content if messages else ""
    # Don't generate response here - let the external AI model handle it
    # Just prepare the system prompt with all the data

    return {
        **state,
        "messages": messages,
        "current_agent": "planning",
        "tools_used": ["get_task_priorities", "get_project_overview", "get_task_details", "get_comprehensive_activity_data", "get_learning_analysis", "get_productivity_insights", "get_time_analysis"],
        "reasoning": "Prepared comprehensive system prompt with task priorities, project status, task details, and recent activities for planning guidance"
    }

def analytics_agent(state: AgentState) -> AgentState:
    """Analytics agent specialized in productivity analysis"""
    messages = state["messages"]
    user_data = state["user_data"]

    # Get comprehensive analytics data using enhanced tools
    metrics = analyze_productivity_metrics(user_data)
    project_overview = get_project_overview(user_data)
    activity_analysis = get_comprehensive_activity_data(user_data)
    task_details = get_task_details(user_data)
    time_analysis = get_time_analysis(user_data)
    project_performance = get_project_performance(user_data)
    learning_analysis = get_learning_analysis(user_data)
    productivity_insights = get_productivity_insights(user_data)
    
    # Create a comprehensive system prompt for analytics
    system_prompt = f"""You are an Analytics Agent specialized in analyzing time tracking, productivity patterns, and performance metrics.

CURRENT DATA:
{metrics}

{project_overview}

{activity_analysis}

{task_details}

{time_analysis}

{project_performance}

{learning_analysis}

{productivity_insights}

YOUR EXPERTISE:
- Time tracking analysis and productivity measurement
- Pattern recognition in work habits and efficiency
- Performance metrics calculation and interpretation
- Trend analysis and forecasting
- Data visualization and reporting
- Comparative analysis and benchmarking
- Root cause analysis of productivity issues

ANALYTICAL CAPABILITIES:
- Calculate productivity ratios and completion rates
- Identify time allocation patterns and inefficiencies
- Analyze task completion trends and bottlenecks
- Measure focus time vs. administrative time
- Track progress velocity and momentum
- Identify peak productivity periods
- Analyze project completion patterns

INSTRUCTIONS:
- Provide data-driven insights and recommendations
- Use specific metrics and percentages when available
- Identify patterns, trends, and anomalies in the data
- Suggest actionable improvements based on analysis
- Create visual representations when helpful (text-based charts)
- Compare current performance to historical data
- Highlight areas of strength and improvement opportunities
- Provide concrete, measurable recommendations

RESPONSE STYLE:
- Lead with key findings and insights
- Use data to support all recommendations
- Include specific numbers and percentages
- Structure analysis logically (overview → details → recommendations)
- Use analytical terminology appropriately
- Provide clear, actionable next steps"""

    messages.append(SystemMessage(content=system_prompt))
    
    # Don't generate response here - let the external AI model handle it
    # Just prepare the system prompt with all the data

    return {
        **state,
        "messages": messages,
        "current_agent": "analytics",
        "tools_used": ["analyze_productivity_metrics", "get_project_overview", "get_comprehensive_activity_data", "get_task_details", "get_time_analysis", "get_project_performance", "get_learning_analysis", "get_productivity_insights"],
        "reasoning": "Prepared comprehensive system prompt with productivity metrics, project status, activity patterns, and task details for analytics response"
    }

def advisor_agent(state: AgentState) -> AgentState:
    """Advisory agent for general productivity advice"""
    messages = state["messages"]
    user_data = state["user_data"]
    
    # Get comprehensive data using enhanced tools
    project_overview = get_project_overview(user_data)
    activities = get_comprehensive_activity_data(user_data)
    priorities = get_task_priorities(user_data)
    learning_analysis = get_learning_analysis(user_data)
    productivity_insights = get_productivity_insights(user_data)
    time_analysis = get_time_analysis(user_data)
    
    # Create a comprehensive system prompt for advisory
    system_prompt = f"""You are an Advisory Agent specialized in providing productivity advice, tips, and best practices.

CURRENT STATE:
{project_overview}

{activities}

{priorities}

{learning_analysis}

{productivity_insights}

{time_analysis}

YOUR EXPERTISE:
- Productivity methodologies and frameworks (GTD, Pomodoro, Time Blocking)
- Workflow optimization and efficiency improvement
- Habit formation and behavior change strategies
- Stress management and work-life balance
- Focus enhancement and distraction management
- Goal setting and achievement strategies
- Communication and collaboration best practices
- Technology tools and automation recommendations

ADVISORY CAPABILITIES:
- Diagnose productivity challenges and bottlenecks
- Recommend personalized productivity systems
- Suggest habit formation strategies
- Provide motivation and accountability guidance
- Offer work-life balance recommendations
- Suggest tool and technology solutions
- Create personalized improvement plans
- Provide ongoing coaching and support

INSTRUCTIONS:
- Provide practical, actionable advice tailored to the user's situation
- Draw from proven productivity methodologies and research
- Offer specific, implementable recommendations
- Consider the user's current workload and constraints
- Suggest gradual improvements rather than overwhelming changes
- Provide motivation and encouragement
- Address both immediate and long-term productivity goals
- Include specific tools, techniques, or resources when relevant

RESPONSE STYLE:
- Be encouraging and supportive
- Use "you" language to make advice personal
- Provide step-by-step guidance when appropriate
- Include specific examples and scenarios
- Balance idealism with practicality
- Ask clarifying questions to better understand needs
- Offer multiple options when applicable
- Focus on sustainable, long-term improvements"""

    messages.append(SystemMessage(content=system_prompt))
    
    # Don't generate response here - let the external AI model handle it
    # Just prepare the system prompt with all the data

    return {
        **state,
        "messages": messages,
        "current_agent": "advisor",
        "tools_used": ["get_project_overview", "get_comprehensive_activity_data", "get_task_priorities", "get_learning_analysis", "get_productivity_insights", "get_time_analysis"],
        "reasoning": "Prepared comprehensive system prompt with project status, activities, and task priorities for advisory response"
    }

def general_assistant(state: AgentState) -> AgentState:
    """General assistant for basic questions with database access"""
    messages = state["messages"]
    user_data = state["user_data"]

    # Get comprehensive overview data using enhanced tools
    project_overview = get_project_overview(user_data)
    activities = get_comprehensive_activity_data(user_data)
    task_details = get_task_details(user_data)
    priorities = get_task_priorities(user_data)
    learning_analysis = get_learning_analysis(user_data)
    productivity_insights = get_productivity_insights(user_data)

    system_prompt = f"""You are a General Assistant that helps with basic questions and provides general assistance.

CURRENT DATA:
{project_overview}

{activities}

{task_details}

{priorities}

{learning_analysis}

{productivity_insights}

YOUR CAPABILITIES:
- Answer general questions and provide information
- Help with basic productivity concepts
- Explain terminology and concepts
- Provide general guidance and support
- Access and analyze user data when relevant
- Connect users with appropriate specialized agents
- Handle miscellaneous requests and inquiries
- Provide insights based on user's actual data

YOUR ROLE:
- Be helpful, friendly, and approachable
- Provide clear, concise answers
- Ask clarifying questions when needed
- Use available data to provide relevant insights
- Direct users to specialized agents when appropriate
- Maintain a helpful and supportive tone
- Focus on being accessible and easy to understand

INSTRUCTIONS:
- Use available data to provide relevant, personalized responses
- If the question is about productivity, planning, or analytics, suggest using the specialized agents
- Provide general guidance when appropriate
- Ask clarifying questions to better understand the user's needs
- Be encouraging and supportive
- Offer to connect users with more specialized help when relevant
- Use actual data to make responses more helpful and specific

RESPONSE STYLE:
- Be conversational and friendly
- Use simple, clear language
- Provide practical, actionable advice when possible
- Ask follow-up questions to better understand needs
- Suggest next steps or additional resources
- Maintain a helpful and encouraging tone
- Reference actual data when relevant to provide more helpful responses"""

    messages.append(SystemMessage(content=system_prompt))

    # Don't generate response here - let the external AI model handle it
    # Just prepare the system prompt with all the data

    return {
        **state,
        "messages": messages,
        "current_agent": "general",
        "tools_used": ["get_project_overview", "get_comprehensive_activity_data", "get_task_details", "get_task_priorities", "get_learning_analysis", "get_productivity_insights"],
        "reasoning": "Prepared comprehensive system prompt with project overview, activities, task details, and priorities for general assistance"
    }

# Agent routing logic
def route_agent(state: AgentState) -> str:
    """Route to appropriate agent based on user input"""
    last_message = state["messages"][-1]
    user_input = last_message.content.lower()
    
    print(f"DEBUG: Routing user input: '{user_input}'")
    
    # Keyword-based routing
    if any(word in user_input for word in ["plan", "schedule", "prioritize", "organize", "deadline", "urgent", "important", "tasks"]):
        print("DEBUG: Routing to planning agent")
        return "planning"
    elif any(word in user_input for word in ["analyze", "time", "productivity", "efficiency", "pattern", "report", "statistics", "metrics", "wasted", "activities", "done", "most", "data"]):
        print("DEBUG: Routing to analytics agent")
        return "analytics"
    elif any(word in user_input for word in ["advice", "tip", "help", "how", "best practice", "suggestion", "recommendation"]):
        print("DEBUG: Routing to advisor agent")
        return "advisor"
    else:
        print("DEBUG: Routing to general agent")
        return "general"

# Create the agent graph
def create_agent_graph():
    """Create the LangGraph agent workflow"""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("planning", planning_agent)
    workflow.add_node("analytics", analytics_agent)
    workflow.add_node("advisor", advisor_agent)
    workflow.add_node("general", general_assistant)
    
    # Set entry point and add routing
    workflow.set_entry_point("general")  # Start with general agent
    
    # Add conditional routing from general agent
    workflow.add_conditional_edges(
        "general",
        route_agent,
        {
            "planning": "planning",
            "analytics": "analytics", 
            "advisor": "advisor",
            "general": END  # Stay in general if no specific routing needed
        }
    )
    
    # All specialized agents end after processing
    workflow.add_edge("planning", END)
    workflow.add_edge("analytics", END)
    workflow.add_edge("advisor", END)
    
    return workflow.compile()

# Global agent graph
agent_graph = create_agent_graph()

@router.post("/agentic-query", response_model=AgenticResponse)
async def agentic_query(
    query: AgenticQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Process query using agentic system"""
    try:
        # Get the selected model
        model = db.query(Model).filter(
            Model.api_key == query.model_api_key,
            Model.owner == current_user.id
        ).first()
        
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")

        # Load user data from database
        from models.projects import Project
        from models.tasks import Task
        from models.activity import Activity
        from models.reminders import Reminder
        
        # Get projects
        projects = db.query(Project).filter(Project.owner == current_user.id).all()
        projects_data = [{"id": p.id, "name": p.name, "color": p.color} for p in projects]
        
        # Get tasks
        tasks = db.query(Task).filter(Task.owner == current_user.id).all()
        tasks_data = [{"id": t.id, "title": t.title, "name": t.title, "state": t.state, "is_urgent": t.is_urgent, "is_important": t.is_important, "deadline": t.deadline.isoformat() if t.deadline else None} for t in tasks]
        
        # Get activities (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        activities = db.query(Activity).filter(
            Activity.clock_in >= thirty_days_ago
        ).order_by(Activity.clock_in.desc()).all()
        
        # Calculate duration and format data
        activities_data = []
        for a in activities:
            duration = 0
            if a.clock_out:
                duration = int((a.clock_out - a.clock_in).total_seconds() / 60)  # duration in minutes
            
            # Get meaningful name from task or description
            activity_name = "Activity"  # default
            if a.description and a.description.strip():
                activity_name = a.description
            elif a.task and a.task.title:
                activity_name = f"Working on: {a.task.title}"
            else:
                # Try to get task title from the task_id
                task = db.query(Task).filter(Task.id == a.task_id).first()
                if task and task.title:
                    activity_name = f"Working on: {task.title}"
            
            activities_data.append({
                "id": a.id, 
                "name": activity_name, 
                "duration": duration, 
                "created_at": a.clock_in.isoformat(),
                "status": a.status,
                "task_id": a.task_id,
                "task_title": a.task.title if a.task else None
            })
        
        # Get reminders
        reminders = db.query(Reminder).filter(Reminder.owner_id == current_user.id).all()
        reminders_data = [{"id": r.id, "title": r.note, "description": r.note, "reminder_time": r.when.isoformat() if r.when else None} for r in reminders]
        
        user_data = {
            "projects": projects_data,
            "tasks": tasks_data,
            "activities": activities_data,
            "reminders": reminders_data
        }
        
        print(f"DEBUG: Loaded {len(projects_data)} projects, {len(tasks_data)} tasks, {len(activities_data)} activities, {len(reminders_data)} reminders")
        
        # Determine which agent to use based on user input
        user_input = query.user_prompt.lower()
        print(f"DEBUG: User input: '{user_input}'")
        
        if any(word in user_input for word in ["plan", "schedule", "prioritize", "organize", "deadline", "urgent", "important", "tasks"]):
            selected_agent = "planning"
            print("DEBUG: Selected planning agent")
        elif any(word in user_input for word in ["analyze", "time", "productivity", "efficiency", "pattern", "report", "statistics", "metrics"]) and not any(word in user_input for word in ["advice", "tip", "help", "how", "best practice", "suggestion", "recommendation"]):
            selected_agent = "analytics"
            print("DEBUG: Selected analytics agent")
        elif any(word in user_input for word in ["advice", "tip", "help", "how", "best practice", "suggestion", "recommendation"]):
            selected_agent = "advisor"
            print("DEBUG: Selected advisor agent")
        else:
            selected_agent = "general"
            print("DEBUG: Selected general agent")
        
        # Create initial state
        initial_state = {
            "messages": [HumanMessage(content=query.user_prompt)],
            "user_data": user_data,
            "current_agent": selected_agent,
            "tools_used": [],
            "reasoning": ""
        }
        
        # Call the appropriate agent to get system prompt and tools
        if selected_agent == "planning":
            result = planning_agent(initial_state)
        elif selected_agent == "analytics":
            result = analytics_agent(initial_state)
        elif selected_agent == "advisor":
            result = advisor_agent(initial_state)
        else:
            result = general_assistant(initial_state)
        
        # Extract system prompt from the agent's messages
        system_messages = [msg for msg in result["messages"] if isinstance(msg, SystemMessage)]
        system_prompt = system_messages[-1].content if system_messages else ""
        
        # Debug: Print system prompt to see what's being sent
        print(f"DEBUG: System prompt length: {len(system_prompt)}")
        print(f"DEBUG: Agent used: {result['current_agent']}")
        print(f"DEBUG: Tools used: {result['tools_used']}")
        print(f"DEBUG: Model base_url: {model.base_url}")
        print(f"DEBUG: Model name: {model.name}")
        
        # Now send the request to the external AI model with the specialized system prompt
        try:
            # Prepare the request payload based on the model type
            if "openai" in model.base_url.lower() or "api.openai.com" in model.base_url:
                # OpenAI-compatible API
                payload = {
                    "model": model.name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query.user_prompt}
                    ],
                    "max_tokens": 4000,
                    "temperature": 0.7
                }
            elif "anthropic" in model.base_url.lower() or "claude" in model.name.lower():
                # Anthropic Claude API
                payload = {
                    "model": model.name,
                    "max_tokens": 4000,
                    "temperature": 0.7,
                    "messages": [
                        {"role": "user", "content": f"{system_prompt}\n\n{query.user_prompt}"}
                    ]
                }
            else:
                # Generic OpenAI-compatible format
                payload = {
                    "model": model.name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query.user_prompt}
                    ],
                    "max_tokens": 4000,
                    "temperature": 0.7
                }

            # Debug: Print payload being sent (truncated)
            print(f"DEBUG: Payload being sent: {str(payload)[:200]}...")
            
            # Make the API request
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {model.api_key}",
                    "Content-Type": "application/json"
                }

                # Determine the correct endpoint based on the base URL
                if model.base_url.endswith('/v1'):
                    endpoint = f"{model.base_url}/chat/completions"
                else:
                    endpoint = f"{model.base_url}/v1/chat/completions"

                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=60.0
                )

                if response.status_code == 200:
                    api_result = response.json()
                    
                    # Extract the response text based on the API format
                    if "choices" in api_result and len(api_result["choices"]) > 0:
                        response_text = api_result["choices"][0]["message"]["content"]
                        # Handle null content (when response is cut off due to token limits)
                        if response_text is None:
                            response_text = "Response was cut off due to token limits. Please try with a shorter prompt or break your request into smaller parts."
                    elif "content" in api_result:
                        response_text = api_result["content"]
                        if response_text is None:
                            response_text = "Response was cut off due to token limits. Please try with a shorter prompt or break your request into smaller parts."
                    else:
                        response_text = str(api_result)

                    return AgenticResponse(
                        response=response_text,
                        agent_used=result["current_agent"],
                        tools_used=result["tools_used"],
                        reasoning=result["reasoning"]
                    )
                else:
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("error", {}).get("message", error_detail)
                    except:
                        pass
                    raise HTTPException(status_code=500, detail=f"AI API error: {error_detail}")
                    
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI processing error: {str(e)}")
        
    except Exception as e:
        print(f"Agentic query error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Agentic processing error: {str(e)}")
