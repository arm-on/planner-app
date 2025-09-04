let currentActivity = null;
let scheduleData = [];
let tasksData = [];
let clockInInterval = null;

// Global data storage
let modelsData = [];
let projectsData = [];
let currentDeadlineFilter = null;

// Tasks pagination and filtering variables
let tasksCurrentPage = 0;
let tasksPageSize = 12; // Show 6 tasks per row, 2 rows = 12 tasks
let tasksTotalCount = 0;
let filteredTasksData = [];

// Task filters
let taskFilters = {
    state: '',
    project: '',
    energy: '',
    importance: '',
    urgency: '',
    deadline: '',
    parent: ''
};

// Pagination variables
let currentPage = 0;
let pageSize = 20;
let totalActivities = 0;
let currentFilter = null; // 'today', 'all', 'date-range'
let currentFilterParams = null; // for date range: {start_date, end_date}

// Activity filter variables
let activityFilters = {
    status: '',
    task: '',
    startDate: '',
    endDate: ''
};

let projectsCurrentPage = 0;
let projectsPageSize = 20;
let modelsCurrentPage = 0;
let modelsPageSize = 20;

// Caches for tasks and projects by ID
let taskCache = {};
let projectCache = {};

let userTimezone = localStorage.getItem('userTimezone') || 'Asia/Tehran';

let availableTimezones = {};
let selectedCountry = '';
let selectedCity = '';
let selectedTimezoneValue = '';
let currentCalendarDate = new Date();

async function fetchAndCacheTask(taskId) {
    if (taskCache[taskId]) return taskCache[taskId];
    try {
        const apiKey = localStorage.getItem('apiKey');
        const response = await fetch(`/tasks/${taskId}`, {
            headers: { 'X-API-Key': apiKey }
        });
        if (response.ok) {
            const task = await response.json();
            taskCache[taskId] = task;
            return task;
        }
    } catch (e) { console.error('Failed to fetch task', taskId, e); }
    return null;
}

async function fetchAndCacheProject(projectId) {
    if (projectCache[projectId]) return projectCache[projectId];
    try {
        const apiKey = localStorage.getItem('apiKey');
        const response = await fetch(`/projects/${projectId}`, {
            headers: { 'X-API-Key': apiKey }
        });
        if (response.ok) {
            const project = await response.json();
            projectCache[projectId] = project;
            return project;
        }
    } catch (e) { console.error('Failed to fetch project', projectId, e); }
    return null;
}

async function ensureTasksAndProjectsForActivities(activities) {
    const missingTaskIds = new Set();
    const missingProjectIds = new Set();
    activities.forEach(a => {
        if (a.task_id && !taskCache[a.task_id]) missingTaskIds.add(a.task_id);
        if (a.project_id && !projectCache[a.project_id]) missingProjectIds.add(a.project_id);
    });
    await Promise.all(Array.from(missingTaskIds).map(fetchAndCacheTask));
    await Promise.all(Array.from(missingProjectIds).map(fetchAndCacheProject));
}

async function ensureTasksForReminders(reminders) {
    const missingTaskIds = new Set();
    reminders.forEach(r => {
        if (r.task_id && !taskCache[r.task_id]) missingTaskIds.add(r.task_id);
    });
    await Promise.all(Array.from(missingTaskIds).map(fetchAndCacheTask));
}

// Toast notification function
function showToast(type, title, message, duration = 5000) {
    const toast = document.getElementById('toast');
    const toastIcon = document.getElementById('toastIcon');
    const toastTitle = document.getElementById('toastTitle');
    const toastBody = document.getElementById('toastBody');
    
    // Set icon and color based on type
    let iconClass = '';
    let bgClass = '';
    
    switch(type) {
        case 'success':
            iconClass = 'bi-check-circle-fill text-success';
            bgClass = 'bg-success text-white';
            break;
        case 'error':
            iconClass = 'bi-exclamation-triangle-fill text-danger';
            bgClass = 'bg-danger text-white';
            break;
        case 'warning':
            iconClass = 'bi-exclamation-circle-fill text-warning';
            bgClass = 'bg-warning text-dark';
            break;
        case 'info':
            iconClass = 'bi-info-circle-fill text-info';
            bgClass = 'bg-info text-white';
            break;
        default:
            iconClass = 'bi-info-circle-fill text-primary';
            bgClass = 'bg-primary text-white';
    }
    
    // Update toast content
    toastIcon.className = `bi ${iconClass}`;
    toastTitle.textContent = title;
    toastBody.textContent = message;
    
    // Update toast styling
    toast.className = `toast ${bgClass}`;
    
    // Show the toast
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: duration
    });
    bsToast.show();
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard initializing...');
    
    // Check API key first
    const apiKey = localStorage.getItem('apiKey');
    console.log('API key found:', !!apiKey);
    
    if (!apiKey) {
        console.log('No API key found, redirecting to login...');
        window.location.href = '/login';
        return;
    }
    
    setTodayDate();
    // Add a small delay to ensure localStorage is available
    setTimeout(() => {
        loadUserInfo();
    }, 100);
    
    // Load all tasks and projects first
    loadAllTasks().then(() => {
        return loadAllProjects();
    }).then(() => {
        return loadModels();
    }).then(async () => {
        await loadUserTimezone();
            // Set filter to today by default
    const userTz = userTimezone || 'Asia/Tehran';
    const now = new Date();
    const today = now.toLocaleDateString('en-CA', { timeZone: userTz });
    currentFilter = 'date-range';
    currentFilterParams = { start_date: today, end_date: today };
    
    // Set the date input fields to today's date
    const startDateInput = document.getElementById('scheduleStartDate');
    const endDateInput = document.getElementById('scheduleEndDate');
    if (startDateInput) startDateInput.value = today;
    if (endDateInput) endDateInput.value = today;
    
    await loadActivitiesWithPagination();
    }).then(async () => {
        await checkForPlannedActivities();
    }).then(async () => {
        await enableActivityButtons();
        populateEditActivityProjectSelect();
    }).catch(error => {
        console.error('Error during dashboard initialization:', error);
    });
    
    setCurrentTime();
    setInterval(setCurrentTime, 1000);
    
    // Update timezone info every minute
    setInterval(updateTimezoneInfo, 60000);
    
    // Fix modal scrolling issues
    setupModalHandlers();

    const newReminderForm = document.getElementById('newReminderForm');
    if (newReminderForm) {
        newReminderForm.addEventListener('submit', function(event) {
            createReminder(event);
        });
    } else {
        console.error('newReminderForm not found!');
    }
    
    const editReminderForm = document.getElementById('editReminderForm');
    if (editReminderForm) {
        editReminderForm.addEventListener('submit', function(event) {
            updateReminder(event);
        });
    } else {
        console.error('editReminderForm not found!');
    }

    // Accessibility fix: blur focus when editActivityModal is hidden
    const editActivityModal = document.getElementById('editActivityModal');
    if (editActivityModal) {
        editActivityModal.addEventListener('hidden.bs.modal', function() {
            if (document.activeElement && this.contains(document.activeElement)) {
                document.activeElement.blur();
            }
        });
    }

    initializeCalendar();
    loadReminders();
});

// Setup modal handlers to prevent scrolling issues
function setupModalHandlers() {
    // Handle modal show events
    document.addEventListener('show.bs.modal', function(event) {
        const modal = event.target;
        const body = document.body;
        
        // Prevent body scroll
        body.style.overflow = 'hidden';
        body.style.paddingRight = '0px';
        
        // Ensure modal is scrollable
        const modalDialog = modal.querySelector('.modal-dialog');
        if (modalDialog) {
            modalDialog.style.maxHeight = '90vh';
            modalDialog.style.overflowY = 'auto';
        }
    });
    
    // Handle modal hide events
    document.addEventListener('hidden.bs.modal', function(event) {
        const body = document.body;
        
        // Restore body scroll
        body.style.overflow = '';
        body.style.paddingRight = '';
    });
    
    // Handle modal shown events
    document.addEventListener('shown.bs.modal', function(event) {
        const modal = event.target;
        
        // Focus on first input if available
        const firstInput = modal.querySelector('input, select, textarea');
        if (firstInput) {
            firstInput.focus();
        }
    });
}

function setTodayDate() {
    const today = new Date();
    const options = { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric',
        timeZone: userTimezone || 'Asia/Tehran'
    };
    document.getElementById('todayDate').textContent = today.toLocaleDateString('en-US', options);
}

function setCurrentTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit',
        timeZone: userTimezone || 'Asia/Tehran'
    });
    
    // Only update the current time if no activity is running
    if (!currentActivity) {
        document.getElementById('currentTime').textContent = timeString;
    }
}

function loadUserInfo() {
    console.log('Loading user info...');
    console.log('All localStorage keys:', Object.keys(localStorage));
    
    const displayName = localStorage.getItem('displayName');
    const username = localStorage.getItem('username');
    const apiKey = localStorage.getItem('apiKey');
    const userId = localStorage.getItem('userId');
    
    console.log('Retrieved from localStorage:', {
        displayName: displayName,
        username: username,
        apiKey: apiKey ? 'present' : 'missing',
        userId: userId
    });
    
    const userName = displayName || username || 'User';
    
    console.log('Final userName:', userName);
    
    const userNameElement = document.getElementById('userName');
    if (userNameElement) {
        userNameElement.textContent = userName;
        console.log('Set userName element to:', userName);
    } else {
        console.error('userName element not found!');
        console.log('Available elements with "user" in id:', 
            Array.from(document.querySelectorAll('[id*="user"]')).map(el => el.id));
    }
}

// Fetch all tasks (no pagination)
async function loadAllTasks() {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
            console.error('No API key found for loading tasks');
            window.location.href = '/login';
            return;
        }
        const response = await fetch('/tasks/?skip=0&limit=10000', {
            headers: { 'X-API-Key': apiKey }
        });
        if (response.ok) {
            tasksData = await response.json();
            // Update taskCache with all tasks
            tasksData.forEach(task => { taskCache[task.id] = task; });
            populateTaskSelect();
            populateParentTaskFilter();
        }
    } catch (error) {
        console.error('Error loading all tasks:', error);
    }
}

// Fetch all projects (no pagination)
async function loadAllProjects() {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
            console.error('No API key found for loading projects');
            return;
        }
        const response = await fetch('/projects/?skip=0&limit=10000', {
            headers: { 'X-API-Key': apiKey }
        });
        if (response.ok) {
            projectsData = await response.json();
            // Update projectCache with all projects
            projectsData.forEach(project => { projectCache[project.id] = project; });
            populateProjectSelects();
            populateActivityProjectSelect();
        }
    } catch (error) {
        console.error('Error loading all projects:', error);
    }
}

// Paginated activities only
async function loadActivitiesWithPagination() {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) return;
        let url = `/activities/?skip=${currentPage * pageSize}&limit=${pageSize}&timezone=${encodeURIComponent(userTimezone || 'Asia/Tehran')}`;
        if (currentFilter === 'date-range' && currentFilterParams) {
            url = `/activities/date-range?start_date=${currentFilterParams.start_date}&end_date=${currentFilterParams.end_date}&skip=${currentPage * pageSize}&limit=${pageSize}&timezone=${encodeURIComponent(userTimezone || 'Asia/Tehran')}`;
        }
        const response = await fetch(url, {
            headers: { 'X-API-Key': apiKey }
        });
        if (response.ok) {
            let activities = await response.json();
            console.log('Received activities:', activities);
            
            console.log('Activity filters being applied:', activityFilters);
            
            // Apply frontend filters for status and task
            if (activityFilters.status || activityFilters.task) {
                console.log('Applying frontend filters...');
                activities = activities.filter(activity => {
                    // Status filter
                    if (activityFilters.status && activity.status !== activityFilters.status) {
                        console.log(`Filtering out activity ${activity.id} due to status mismatch: ${activity.status} !== ${activityFilters.status}`);
                        return false;
                    }
                    
                    // Task filter
                    if (activityFilters.task && Number(activity.task_id) !== Number(activityFilters.task)) {
                        console.log(`Filtering out activity ${activity.id} due to task mismatch: ${activity.task_id} !== ${activityFilters.task}`);
                        return false;
                    }
                    
                    return true;
                });
            }
            
            console.log('Filtered activities:', activities);
            console.log('Activities count:', activities.length);
            console.log('Activity dates:', activities.map(a => new Date(a.clock_in).toDateString()));
            scheduleData = activities;
            console.log('Updated scheduleData:', scheduleData);
            console.log('scheduleData count:', scheduleData.length);
            setCurrentDoingActivityFromSchedule();
            displaySchedule();
            
            // Load total count
            await loadTotalCount();
        } else {
            console.error('Failed to load activities:', response.status, response.statusText);
        }
    } catch (error) {
        console.error('Error loading activities:', error);
    }
}

async function loadTotalCount() {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) return;
        
        let url = '/activities/count';
        if (currentFilter === 'date-range' && currentFilterParams) {
            url = `/activities/count?start_date=${currentFilterParams.start_date}&end_date=${currentFilterParams.end_date}&timezone=${encodeURIComponent(userTimezone || 'Asia/Tehran')}`;
        }
        
        const response = await fetch(url, {
            headers: {
                'X-API-Key': apiKey
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            let count = data.count;
            
            // If we have frontend filters, we need to adjust the count
            // For now, we'll use the filtered activities count
            if (activityFilters.status || activityFilters.task) {
                count = scheduleData.length;
            }
            
            totalActivities = count;
            updatePaginationInfo();
        }
    } catch (error) {
        console.error('Error loading total count:', error);
    }
}

function previousPage() {
    if (currentPage > 0) {
        currentPage--;
        loadActivitiesWithPagination();
    }
}

function nextPage() {
    const maxPage = Math.ceil(totalActivities / pageSize) - 1;
    if (currentPage < maxPage) {
        currentPage++;
        loadActivitiesWithPagination();
    }
}

async function startNearestScheduledActivity() {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
            showToast('error', 'Error', 'No API key found. Please log in again.');
            window.location.href = '/login';
            return;
        }
        
        // Get all activities to find the one that includes current datetime
        const response = await fetch('/activities/', {
            headers: {
                'X-API-Key': apiKey
            }
        });
        
        if (response.ok) {
            const allActivities = await response.json();
            const now = new Date();
            
            // Filter for PLANNED activities that include the current datetime
            const currentActivities = allActivities.filter(activity => {
                if (activity.status !== 'PLANNED') return false;
                
                const clockIn = new Date(activity.clock_in);
                const clockOut = activity.clock_out ? new Date(activity.clock_out) : null;
                
                // Check if current time is within the activity's scheduled time range
                if (clockOut) {
                    // Activity has both start and end time - check if now is within range
                    return now >= clockIn && now <= clockOut;
                } else {
                    // Activity only has start time - check if now is at or after start time
                    // and within a reasonable window (e.g., 2 hours after start time)
                    const twoHoursLater = new Date(clockIn.getTime() + 2 * 60 * 60 * 1000);
                    return now >= clockIn && now <= twoHoursLater;
                }
            });
            
            if (currentActivities.length === 0) {
                showToast('info', 'No Current Activities', 'No planned activities are currently scheduled for this time. Check your schedule.');
                return;
            }
            
            // If multiple activities overlap, find the one with the earliest start time
            let bestActivity = currentActivities[0];
            let earliestStart = new Date(bestActivity.clock_in);
            
            currentActivities.forEach(activity => {
                const activityStart = new Date(activity.clock_in);
                if (activityStart < earliestStart) {
                    earliestStart = activityStart;
                    bestActivity = activity;
                }
            });
            
            if (bestActivity) {
                // Get task and project info for better feedback
                const task = tasksData.find(t => Number(t.id) === Number(bestActivity.task_id));
                const taskTitle = task ? task.title : 'Unknown Task';
                
                // Start the activity
                await startScheduledActivity(bestActivity.id);
                showToast('success', 'Activity Started', `Started: ${taskTitle} - ${bestActivity.description || 'Scheduled Activity'}`);
            } else {
                showToast('info', 'No Activities Found', 'No suitable activities found to start.');
            }
        }
    } catch (error) {
        console.error('Error starting current scheduled activity:', error);
        showToast('error', 'Error', 'Failed to start current activity');
    }
}

async function startScheduledActivity(activityId) {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
            showToast('error', 'Error', 'No API key found. Please log in again.');
            window.location.href = '/login';
            return;
        }

        // Update the activity status to DOING and set clock_in to now
        const now = new Date().toISOString();
        const response = await fetch(`/activities/${activityId}`, {
            method: 'PUT',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                status: 'DOING',
                clock_in: now
            })
        });

        if (response.ok) {
            // Set as current activity with updated clock_in time
            const updatedActivity = await response.json();
            console.log('Updated activity from API:', updatedActivity);
            console.log('Updated clock_in time:', updatedActivity.clock_in);
            currentActivity = updatedActivity;
            
            // Update the display with the new start time
            updateCurrentActivityDisplay(true);
            await enableActivityButtons();
            startClockInTimer();
            
            // Reload schedule to show updated status
            await loadActivitiesWithPagination();
            
            showToast('success', 'Success!', 'Activity started successfully!');
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to start activity: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error starting activity:', error);
        showToast('error', 'Error', `Error starting activity: ${error.message}`);
    }
}

async function clockInActivity(activityId) {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
            alert('No API key found. Please log in again.');
            window.location.href = '/login';
            return;
        }

        // Update the activity status to DOING and set clock_in to now
        const now = new Date().toISOString();
        const response = await fetch(`/activities/${activityId}`, {
            method: 'PUT',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                status: 'DOING',
                clock_in: now
            })
        });

        if (response.ok) {
            // Set as current activity
            const updatedActivity = await response.json();
            console.log('Updated activity from API (clockIn):', updatedActivity);
            console.log('Updated clock_in time (clockIn):', updatedActivity.clock_in);
            currentActivity = updatedActivity;
            updateCurrentActivityDisplay(true);
            await enableActivityButtons();
            startClockInTimer();
            
            // Reload schedule to show updated status
            await loadActivitiesWithPagination();
            
            showToast('success', 'Success!', 'Successfully clocked in!');
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to clock in: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error clocking in:', error);
        showToast('error', 'Error', `Error clocking in: ${error.message}`);
    }
}

async function startActivity(taskId, status, clockIn, isScheduled = false, clockOut = null, description = null, isRecurring = false, daysInterval = null, recurrenceCount = null) {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
            alert('No API key found. Please log in again.');
            window.location.href = '/login';
            return;
        }

        // If starting an activity (not just creating), set status to DOING
        const finalStatus = isScheduled ? 'DOING' : status;

        const requestBody = {
            task_id: taskId,
            status: finalStatus,
            clock_in: clockIn.toISOString(),
            clock_out: clockOut ? clockOut.toISOString() : null,
            description: description || null,
            is_recurring: isRecurring,
            days_interval: daysInterval,
            recurrence_count: recurrenceCount
        };

        console.log('Creating activity with data:', requestBody);

        // --- Update task state to 'doing' if activity is being started ---
        if (finalStatus === 'DOING') {
            await fetch(`/tasks/${taskId}`, {
                method: 'PUT',
                headers: {
                    'X-API-Key': apiKey,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ state: 'doing' })
            });
        }
        // --- End update task state ---

        const response = await fetch('/activities/', {
            method: 'POST',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        console.log('Response status:', response.status);

        if (response.ok) {
            const newActivities = await response.json();
            console.log('Activities created:', newActivities);
            
            // Show success message with count of created activities
            const activityCount = newActivities.length;
            if (activityCount > 1) {
                showToast('success', 'Success!', `Created ${activityCount} activities successfully!`);
            } else {
                showToast('success', 'Success!', 'Activity created successfully!');
            }
            
            // Only set as current activity if it's actually being started (DOING status) and it's the first activity
            if (finalStatus === 'DOING' && newActivities.length > 0) {
                currentActivity = newActivities[0];
                updateCurrentActivityDisplay(isScheduled);
                await enableActivityButtons();
                startClockInTimer();
            }
            
            // Reload schedule to show new activities
            await loadActivitiesWithPagination();
            // Refresh dashboard data without page reload
            await refreshDashboardData();
        } else {
            const errorData = await response.json();
            console.error('Error response:', errorData);
            showToast('error', 'Error', `Failed to create activity: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error starting activity:', error);
        showToast('error', 'Error', `Error creating activity: ${error.message}`);
    }
}

function updateCurrentActivityDisplay(isScheduled) {
    console.log('updateCurrentActivityDisplay called with currentActivity:', currentActivity);
    console.log('tasksData available:', tasksData);
    console.log('tasksData length:', tasksData ? tasksData.length : 'undefined');
    
    const task = tasksData ? tasksData.find(t => Number(t.id) === Number(currentActivity.task_id)) : null;
    console.log('Found task for activity:', task);
    
    const startTime = new Date(currentActivity.clock_in).toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        timeZone: userTimezone || 'Asia/Tehran'
    });

    const taskTitle = task ? task.title : `Task ID ${currentActivity.task_id}`;
    console.log('Using task title:', taskTitle);

    document.getElementById('currentActivityInfo').innerHTML = `
        <h6 class="mb-1">${taskTitle}</h6>
        <p class="mb-1">You're doing this activity since ${startTime}</p>
        <span class="badge ${isScheduled ? 'bg-success' : 'bg-warning'}">
            ${isScheduled ? 'On Schedule' : 'Off Schedule'}
        </span>
        <span class="badge bg-warning ms-2">DOING</span>
    `;

    // Set the fixed start time (don't change this)
    document.getElementById('startTime').textContent = startTime;
}

async function checkForPlannedActivities() {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) return false;
        
        const response = await fetch('/activities/', {
            headers: {
                'X-API-Key': apiKey
            }
        });
        
        if (response.ok) {
            const allActivities = await response.json();
            const now = new Date();
            
            // Check for PLANNED activities that include the current datetime
            const currentActivities = allActivities.filter(activity => {
                if (activity.status !== 'PLANNED') return false;
                
                const clockIn = new Date(activity.clock_in);
                const clockOut = activity.clock_out ? new Date(activity.clock_out) : null;
                
                // Check if current time is within the activity's scheduled time range
                if (clockOut) {
                    // Activity has both start and end time - check if now is within range
                    return now >= clockIn && now <= clockOut;
                } else {
                    // Activity only has start time - check if now is at or after start time
                    // and within a reasonable window (e.g., 2 hours after start time)
                    const twoHoursLater = new Date(clockIn.getTime() + 2 * 60 * 60 * 1000);
                    return now >= clockIn && now <= twoHoursLater;
                }
            });
            
            return currentActivities.length > 0;
        }
        return false;
    } catch (error) {
        console.error('Error checking for planned activities:', error);
        return false;
    }
}

async function enableActivityButtons() {
    console.log('Enabling activity buttons');
    const onScheduleBtn = document.getElementById('onScheduleBtn');
    const clockOutBtn = document.getElementById('clockOutBtn');
    
    // Enable clock out button if there's a current activity
    if (clockOutBtn) clockOutBtn.disabled = !currentActivity;
    
    // Enable on schedule button if there are planned activities and no current activity
    if (onScheduleBtn) {
        const hasPlannedActivities = await checkForPlannedActivities();
        onScheduleBtn.disabled = !hasPlannedActivities || currentActivity;
        
        // Update button text based on state
        if (hasPlannedActivities && !currentActivity) {
            onScheduleBtn.innerHTML = '<i class="bi bi-play-circle me-2"></i>Start Current Activity';
        } else if (currentActivity) {
            onScheduleBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>On Schedule';
        } else {
            onScheduleBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>On Schedule';
        }
    }
    
    console.log('Buttons enabled - onSchedule:', !onScheduleBtn?.disabled, 'clockOut:', !clockOutBtn?.disabled);
}

function startClockInTimer() {
    if (clockInInterval) clearInterval(clockInInterval);
    
    clockInInterval = setInterval(() => {
        if (currentActivity) {
            const startTime = new Date(currentActivity.clock_in);
            const now = new Date();
            const durationMs = now - startTime;
            const durationMinutes = Math.floor(durationMs / 1000 / 60);
            const hours = Math.floor(durationMinutes / 60);
            const minutes = durationMinutes % 60;
            
            console.log('Timer debug - startTime:', startTime, 'now:', now, 'durationMs:', durationMs, 'hours:', hours, 'minutes:', minutes);
            
            // Display elapsed time in HH:MM format
            document.getElementById('currentTime').textContent = 
                `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
        }
    }, 1000);
}

// Event Listeners
// document.getElementById('onScheduleBtn').addEventListener('click', async function() {
//     if (currentActivity) {
//         updateCurrentActivityDisplay(true);
//     } else {
//         // Find and start the nearest scheduled activity
//         await startNearestScheduledActivity();
//     }
// });

document.getElementById('clockOutBtn').addEventListener('click', async function() {
    console.log('Clock out button clicked!');
    console.log('Current activity:', currentActivity);
    
    if (!currentActivity) {
        console.log('No current activity to clock out');
        return;
    }

    console.log('Clock out button clicked for activity:', currentActivity.id);

    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
            alert('No API key found. Please log in again.');
            window.location.href = '/login';
            return;
        }

        const clockOutData = {
            clock_out: new Date().toISOString(),
            status: 'DONE'
        };

        console.log('Sending clock out data:', clockOutData);
        console.log('Current activity before clock out:', currentActivity);

        // --- Update task state to 'done' when clocking out ---
        if (currentActivity.task_id) {
            await fetch(`/tasks/${currentActivity.task_id}`, {
                method: 'PUT',
                headers: {
                    'X-API-Key': apiKey,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ state: 'done' })
            });
        }
        // --- End update task state ---

        const response = await fetch(`/activities/${currentActivity.id}`, {
            method: 'PUT',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(clockOutData)
        });

        console.log('Clock out response status:', response.status);

        if (response.ok) {
            const updatedActivity = await response.json();
            console.log('Activity updated successfully:', updatedActivity);
            console.log('Updated activity status:', updatedActivity.status);
            
            // Reset current activity
            currentActivity = null;
            document.getElementById('currentActivityInfo').innerHTML = `
                <p class="mb-1">No active activity</p>
                <small>Click "Clock In" to start tracking your work</small>
            `;
            document.getElementById('currentTime').textContent = '--:--';
            document.getElementById('startTime').textContent = '--:--';
            
            // Disable buttons
            const onScheduleBtn = document.getElementById('onScheduleBtn');
            if (onScheduleBtn) onScheduleBtn.disabled = true;
            const clockOutBtn = document.getElementById('clockOutBtn');
            if (clockOutBtn) clockOutBtn.disabled = true;
            
            // Re-enable on schedule button if there are planned activities
            await enableActivityButtons();
            
            if (clockInInterval) clearInterval(clockInInterval);
            
            // Resume normal time display
            setCurrentTime();
            
            // Reload schedule to show updated status
            await loadActivitiesWithPagination();
            
            // Double-check current activity state from server
            await checkForPlannedActivities();
            
            showToast('success', 'Success!', 'Successfully clocked out!');
        } else {
            // Handle error response - only read the body once
            let errorMessage = `Server error (${response.status}): ${response.statusText}`;
            
            // Try to get more detailed error information
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || errorMessage;
                } catch (parseError) {
                    console.error('Failed to parse JSON error response:', parseError);
                }
            } else {
                try {
                    const textResponse = await response.text();
                    errorMessage = `Server error (${response.status}): ${textResponse.substring(0, 100)}`;
                } catch (textError) {
                    console.error('Failed to read text error response:', textError);
                }
            }
            
            console.error('Failed to clock out:', errorMessage);
            showToast('error', 'Error', `Failed to clock out: ${errorMessage}`);
        }
    } catch (error) {
        console.error('Error clocking out:', error);
        showToast('error', 'Error', `Error clocking out: ${error.message}`);
    }
});

const startActivityBtn = document.getElementById('startActivityBtn');
if (!startActivityBtn) {
    console.error('startActivityBtn element not found!');
} else {

startActivityBtn.addEventListener('click', async function() {
    console.log('Create Activity button clicked!');
    
    const taskSelect = document.getElementById('activityTask');
    const statusSelect = document.getElementById('activityStatus');
    const clockInInput = document.getElementById('activityClockIn');
    const clockOutInput = document.getElementById('activityClockOut');
    
    console.log('Form elements found:', {
        taskSelect: !!taskSelect,
        statusSelect: !!statusSelect,
        clockInInput: !!clockInInput,
        clockOutInput: !!clockOutInput
    });
    
    if (!taskSelect || !statusSelect || !clockInInput) {
        console.error('One or more form elements not found!');
        showToast('error', 'Error', 'Form elements not found. Please refresh the page.');
        return;
    }
    
    const projectId = document.getElementById('activityProject').value;
    const taskId = taskSelect.value;
    const status = statusSelect.value;
    const clockIn = clockInInput.value;
    const clockOut = clockOutInput.value;
    const description = document.getElementById('activityDescription').value;
    
    // Get recurring fields
    const isRecurring = document.getElementById('activityRecurring').checked;
    const daysInterval = isRecurring ? parseInt(document.getElementById('activityDaysInterval').value) : null;
    const recurrenceCount = isRecurring ? parseInt(document.getElementById('activityRecurrenceCount').value) : null;

    console.log('Form values:', { projectId, taskId, status, clockIn, clockOut, isRecurring, daysInterval, recurrenceCount });

    if (!projectId || !taskId || !clockIn) {
        console.log('Missing required fields');
        showToast('warning', 'Validation Error', 'Please fill in all required fields');
        return;
    }

    // Validate that a project is selected
    if (projectId === '') {
        console.log('No project selected');
        showToast('warning', 'Validation Error', 'Please select a project');
        return;
    }

    // Validate that a task is selected
    if (taskId === '') {
        console.log('No task selected');
        showToast('warning', 'Validation Error', 'Please select a task');
        return;
    }

    // Validate clock in time
    const clockInDate = new Date(clockIn);
    if (isNaN(clockInDate.getTime())) {
        console.log('Invalid clock in time:', clockIn);
        showToast('warning', 'Validation Error', 'Please enter a valid clock in time');
        return;
    }

    // Validate clock out time if required
    let clockOutDate = null;
    if (status === 'DONE' && !clockOut) {
        console.log('Clock out time required for DONE status');
        showToast('warning', 'Validation Error', 'Clock out time is required for completed activities');
        return;
    }
    
    if (clockOut) {
        clockOutDate = new Date(clockOut);
        if (isNaN(clockOutDate.getTime())) {
            console.log('Invalid clock out time:', clockOut);
            showToast('warning', 'Validation Error', 'Please enter a valid clock out time');
            return;
        }
        
        // Ensure clock out is after clock in
        if (clockOutDate <= clockInDate) {
            console.log('Clock out must be after clock in');
            showToast('warning', 'Validation Error', 'Clock out time must be after clock in time');
            return;
        }
    }
    
    // Validate recurring fields if recurring is enabled
    if (isRecurring) {
        if (!daysInterval || daysInterval <= 0) {
            console.log('Invalid days interval:', daysInterval);
            showToast('warning', 'Validation Error', 'Days interval must be greater than 0');
            return;
        }
        if (!recurrenceCount || recurrenceCount <= 0) {
            console.log('Invalid recurrence count:', recurrenceCount);
            showToast('warning', 'Validation Error', 'Recurrence count must be greater than 0');
            return;
        }
    }

    console.log('Starting activity with:', { taskId, status, clockIn, clockInDate, clockOut, clockOutDate, description, isRecurring, daysInterval, recurrenceCount });

    try {
        await startActivity(parseInt(taskId), status, clockInDate, false, clockOutDate, description, isRecurring, daysInterval, recurrenceCount);
        
        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('newActivityModal'));
        modal.hide();
        
        // Reset form
        document.getElementById('newActivityForm').reset();
        
        // Reset task select to disabled state
        const taskSelect = document.getElementById('activityTask');
        if (taskSelect) {
            taskSelect.innerHTML = '<option value="">Choose a task...</option>';
            taskSelect.disabled = true;
        }
        
        // Set default clock in time to now
        setDefaultClockInTime();
        
        // Reset recurring fields
        document.getElementById('activityRecurring').checked = false;
        document.getElementById('recurringFields').style.display = 'none';
        
        // Update form fields to show proper visibility based on current status
        updateActivityFormFields();
    } catch (error) {
        console.error('Error in startActivityBtn:', error);
        showToast('error', 'Error', `Error creating activity: ${error.message}`);
    }
});
}

// Set default clock in time to now in app timezone
function setDefaultClockInTime() {
    const now = new Date();
    const defaultTime = formatDateTimeForInput(now);
    document.getElementById('activityClockIn').value = defaultTime;
}

// Update activity form fields based on status
function updateActivityFormFields() {
    const status = document.getElementById('activityStatus').value;
    const clockInField = document.getElementById('clockInField');
    const clockOutField = document.getElementById('clockOutField');
    const clockInInput = document.getElementById('activityClockIn');
    const clockOutInput = document.getElementById('activityClockOut');
    
    console.log('updateActivityFormFields called with status:', status);
    console.log('clockOutField element:', clockOutField);
    
    // Reset required attributes
    clockInInput.required = true;
    clockOutInput.required = false;
    
    switch(status) {
        case 'PLANNED':
            // Show both clock in and clock out fields
            console.log('PLANNED status: showing both fields');
            clockInField.style.display = 'block';
            clockOutField.style.display = 'block';
            clockInInput.required = true;
            clockOutInput.required = false; // Optional for planned
            break;
            
        case 'DOING':
            // Show only clock in, set it to now
            console.log('DOING status: hiding clock out field');
            clockInField.style.display = 'block';
            clockOutField.style.display = 'none';
            clockInInput.required = true;
            clockOutInput.required = false;
            // Set clock in to current time
            setDefaultClockInTime();
            break;
            
        case 'DONE':
            // Show both fields, both required
            console.log('DONE status: showing both fields');
            clockInField.style.display = 'block';
            clockOutField.style.display = 'block';
            clockInInput.required = true;
            clockOutInput.required = true;
            break;
    }
}

// Set default clock in time to now
setDefaultClockInTime();

// Initialize form fields when modal opens
document.addEventListener('DOMContentLoaded', function() {
    // Initialize activity form fields
    updateActivityFormFields();
    
    // Add specific handler for newActivityModal to ensure proper initialization
    const newActivityModal = document.getElementById('newActivityModal');
    if (newActivityModal) {
        newActivityModal.addEventListener('shown.bs.modal', function() {
            console.log('newActivityModal shown event triggered');
            // Ensure form fields are properly initialized when modal opens
            updateActivityFormFields();
            setDefaultClockInTime();
        });
    }
});

// Toggle recurring fields visibility
function toggleRecurringFields() {
    const isRecurring = document.getElementById('activityRecurring').checked;
    const recurringFields = document.getElementById('recurringFields');
    
    if (isRecurring) {
        recurringFields.style.display = 'block';
    } else {
        recurringFields.style.display = 'none';
    }
}

// Filter schedule by date range
async function filterScheduleByDate() {
    const startDate = document.getElementById('scheduleStartDate').value;
    const endDate = document.getElementById('scheduleEndDate').value;
    
    if (!startDate || !endDate) {
        showToast('warning', 'Validation Error', 'Please select both start and end dates');
        return;
    }
    
    if (new Date(startDate) > new Date(endDate)) {
        showToast('warning', 'Validation Error', 'Start date must be before end date');
        return;
    }
    
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) return;

        // Use the new backend endpoint for better performance
        console.log('Filtering activities with dates:', { startDate, endDate });
        const response = await fetch(`/activities/date-range?start_date=${startDate}&end_date=${endDate}`, {
            headers: {
                'X-API-Key': apiKey
            }
        });

        if (response.ok) {
            // Reset pagination for date range view
            currentPage = 0;
            currentFilter = 'date-range';
            currentFilterParams = { start_date: startDate, end_date: endDate };
            
            await loadActivitiesWithPagination();
            document.getElementById('scheduleTitle').textContent = `Activities (${startDate} to ${endDate})`;
            
            // Update button text
            const button = document.getElementById('toggleActivitiesBtn');
            if (button) {
                button.innerHTML = '<i class="bi bi-calendar-check me-1"></i>Show All Activities';
                button.onclick = showAllActivities;
            }
            
            showToast('info', 'Filter Applied', `Showing activities from ${startDate} to ${endDate}`);
        } else {
            console.log('Filter response status:', response.status);
            let errorMessage = 'Unknown error';
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || 'Unknown error';
                console.log('Filter error data:', errorData);
            } catch (parseError) {
                const textResponse = await response.text();
                errorMessage = `Server error (${response.status}): ${textResponse.substring(0, 100)}`;
                console.log('Filter text response:', textResponse);
            }
            showToast('error', 'Error', `Failed to filter activities: ${errorMessage}`);
        }
    } catch (error) {
        console.error('Error filtering schedule:', error);
        showToast('error', 'Error', 'Failed to filter activities');
    }
}

// Clear schedule filter
async function clearScheduleFilter() {
    document.getElementById('scheduleStartDate').value = '';
    document.getElementById('scheduleEndDate').value = '';
    currentPage = 0;
    currentFilter = 'today';
    currentFilterParams = null;
    await loadActivitiesWithPagination();
    showToast('info', 'Filter Cleared', 'Showing today\'s activities');
}

// Apply activity filters
async function applyActivityFilters() {
    const status = document.getElementById('activityStatusFilter').value;
    const task = document.getElementById('activityTaskFilter').value;
    const startDate = document.getElementById('scheduleStartDate').value;
    const endDate = document.getElementById('scheduleEndDate').value;
    
    // Update filter object
    activityFilters = {
        status: status,
        task: task,
        startDate: startDate,
        endDate: endDate
    };
    
    // Reset pagination
    currentPage = 0;
    
    // Determine filter type and load activities
    if (startDate && endDate) {
        // Date range filter
        if (new Date(startDate) > new Date(endDate)) {
            showToast('warning', 'Validation Error', 'Start date must be before end date');
            return;
        }
        
        currentFilter = 'date-range';
        currentFilterParams = { start_date: startDate, end_date: endDate };
        await loadActivitiesWithPagination();
        document.getElementById('scheduleTitle').textContent = `Activities (${startDate} to ${endDate})`;
    } else {
        // All activities with status/task filters
        currentFilter = 'all';
        currentFilterParams = null;
        await loadActivitiesWithPagination();
        document.getElementById('scheduleTitle').textContent = 'All Activities';
    }
    
    // Update button text
    const button = document.getElementById('toggleActivitiesBtn');
    if (button) {
        button.innerHTML = '<i class="bi bi-calendar-check me-1"></i>Show Today Only';
        button.onclick = showTodayOnly;
    }
    
    // Show filter applied message
    let filterMessage = 'Filters applied';
    if (status || task || startDate || endDate) {
        const filters = [];
        if (status) filters.push(`Status: ${status}`);
        if (task) {
            const taskName = tasksData.find(t => Number(t.id) === Number(task))?.title || 'Unknown Task';
            filters.push(`Task: ${taskName}`);
        }
        if (startDate && endDate) filters.push(`Date: ${startDate} to ${endDate}`);
        filterMessage = `Showing activities with: ${filters.join(', ')}`;
    }
    
    showToast('info', 'Filter Applied', filterMessage);
}

// Clear activity filters
async function clearActivityFilters() {
    // Clear all filter inputs
    document.getElementById('activityStatusFilter').value = '';
    document.getElementById('activityTaskFilter').value = '';
    document.getElementById('scheduleStartDate').value = '';
    document.getElementById('scheduleEndDate').value = '';
    
    // Clear filter object
    activityFilters = {
        status: '',
        task: '',
        startDate: '',
        endDate: ''
    };
    
    // Reset to today's view
    currentPage = 0;
    currentFilter = 'today';
    currentFilterParams = null;
    await loadActivitiesWithPagination();
    
    showToast('info', 'Filters Cleared', 'Showing today\'s activities');
}

// Populate activity task filter
function populateActivityTaskFilter() {
    const taskFilter = document.getElementById('activityTaskFilter');
    if (taskFilter) {
        taskFilter.innerHTML = '<option value="">All Tasks</option>';
        tasksData.forEach(task => {
            const option = document.createElement('option');
            option.value = task.id;
            option.textContent = task.title;
            taskFilter.appendChild(option);
        });
    }
}

// Load Models
async function loadModels(page = 0) {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) return;
        let url = `/models/?skip=${page * modelsPageSize}&limit=${modelsPageSize}`;
        const response = await fetch(url, {
            headers: {
                'X-API-Key': apiKey
            }
        });
        if (response.ok) {
            modelsData = await response.json();
            modelsCurrentPage = page;
            displayModelsList();
        }
    } catch (error) {
        console.error('Error loading models:', error);
    }
}

function modelsPreviousPage() {
    if (modelsCurrentPage > 0) {
        modelsCurrentPage--;
        loadModels(modelsCurrentPage);
    }
}

function modelsNextPage() {
    if ((modelsCurrentPage + 1) * modelsPageSize < modelsData.length) {
        modelsCurrentPage++;
        loadModels(modelsCurrentPage);
    }
}

// Load Projects
async function loadProjects(page = 0) {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
            console.error('No API key found for loading projects');
            return;
        }
        console.log('Loading projects with API key:', apiKey);
        let url = `/projects/?skip=${page * projectsPageSize}&limit=${projectsPageSize}`;
        const response = await fetch(url, {
            headers: {
                'X-API-Key': apiKey
            }
        });
        console.log('Projects response status:', response.status);
        if (response.ok) {
            projectsData = await response.json();
            projectsCurrentPage = page;
            populateProjectSelects();
            populateActivityProjectSelect();
        }
    } catch (error) {
        console.error('Error loading projects:', error);
    }
}

function projectsPreviousPage() {
    if (projectsCurrentPage > 0) {
        projectsCurrentPage--;
        loadProjects(projectsCurrentPage);
    }
}

function projectsNextPage() {
    if ((projectsCurrentPage + 1) * projectsPageSize < projectsData.length) {
        projectsCurrentPage++;
        loadProjects(projectsCurrentPage);
    }
}

// Populate project selects in forms
function populateProjectSelects() {
    // Populate task form project select
    const taskProjectSelect = document.getElementById('taskProject');
    if (taskProjectSelect) {
        taskProjectSelect.innerHTML = '<option value="">Select project...</option>';
        projectsData.forEach(project => {
            const option = document.createElement('option');
            option.value = project.id;
            option.textContent = project.name;
            taskProjectSelect.appendChild(option);
        });
    }
    
    // Populate task filters
    populateTaskFilters();
    
    // Display projects list in modal
    displayProjectsList();
    
    // Also display tasks list now that projects are loaded
    if (tasksData && tasksData.length > 0) {
        console.log('Projects loaded, now displaying tasks list with project names');
        displayTasksList();
    }
}

// Populate task select for activity forms
function populateTaskSelect() {
    const select = document.getElementById('activityTask');
    const showDoneCheckbox = document.getElementById('showDoneTasksCheckbox');
    const projectSelect = document.getElementById('activityProject');
    if (select) {
        select.innerHTML = '<option value="">Choose a task...</option>';
        const showDone = showDoneCheckbox && showDoneCheckbox.checked;
        const selectedProjectId = projectSelect ? projectSelect.value : '';
        let availableTasks = [];
        if (showDone) {
            // Only show done tasks for the selected project
            if (selectedProjectId) {
                availableTasks = tasksData.filter(task => task.state === 'done' && String(task.proj_id) === String(selectedProjectId));
            } else {
                availableTasks = [];
            }
        } else {
            // Only show open/active tasks for the selected project
            if (selectedProjectId) {
                availableTasks = tasksData.filter(task => task.state !== 'done' && task.state !== 'closed' && String(task.proj_id) === String(selectedProjectId));
            } else {
                availableTasks = [];
            }
        }
        availableTasks.forEach(task => {
            const option = document.createElement('option');
            option.value = task.id;
            option.textContent = task.title;
            select.appendChild(option);
        });
    }
    if (projectsData && projectsData.length > 0) {
        displayTasksList();
    }
}

// Add event listener for the showDoneTasksCheckbox
const showDoneCheckbox = document.getElementById('showDoneTasksCheckbox');
if (showDoneCheckbox) {
    showDoneCheckbox.addEventListener('change', populateTaskSelect);
}

// Display models list
function displayModelsList() {
    const modelsListDiv = document.getElementById('modelsList');
    
    if (modelsData.length === 0) {
        modelsListDiv.innerHTML = '<p class="text-muted text-center">No models found</p>';
        return;
    }

    let html = '<div class="row">';
    modelsData.forEach(model => {
        html += `
            <div class="col-md-6 mb-3">
                <div class="card">
                    <div class="card-body">
                        <h6 class="card-title">${model.name}</h6>
                        <p class="text-muted mb-2">Base URL: ${model.base_url}</p>
                        <div class="d-flex justify-content-between align-items-center">
                            <small class="text-muted">API Key: ${model.api_key.substring(0, 8)}...</small>
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-outline-warning btn-sm" onclick="editModel('${model.api_key}')" title="Edit Model">
                                    <i class="bi bi-pencil"></i>
                                </button>
                                <button class="btn btn-outline-danger btn-sm" onclick="deleteModel('${model.api_key}')" title="Delete Model">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    modelsListDiv.innerHTML = html;
}

// Display projects list
function displayProjectsList() {
    const projectsListDiv = document.getElementById('projectsList');
    if (projectsData.length === 0) {
        projectsListDiv.innerHTML = '<p class="text-muted text-center">No projects found</p>';
        return;
    }
    let html = '<ul class="list-group">';
    projectsData.forEach(project => {
        html += `
            <li class="list-group-item d-flex justify-content-between align-items-center py-2">
                <span>
                    <span class="color-indicator me-2" style="display:inline-block;width:14px;height:14px;background-color:${project.color};border-radius:50%;vertical-align:middle;"></span>
                    <span style="vertical-align:middle;">${project.name}</span>
                </span>
                <span>
                    <button class="btn btn-outline-warning btn-sm me-1" onclick="editProject(${project.id})" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-outline-danger btn-sm" onclick="deleteProject(${project.id})" title="Delete">
                        <i class="bi bi-trash"></i>
                    </button>
                </span>
            </li>
        `;
    });
    html += '</ul>';
    projectsListDiv.innerHTML = html;
}

// Display tasks list with pagination and filtering
function displayTasksList() {
    const tasksListDiv = document.getElementById('tasksList');
    const tasksPaginationDiv = document.getElementById('tasksPagination');
    
    // Apply all filters
    filteredTasksData = applyTaskFiltersToData(tasksData);
    tasksTotalCount = filteredTasksData.length;
    
    if (filteredTasksData.length === 0) {
        tasksListDiv.innerHTML = `<p class="text-muted text-center">No tasks found matching the current filters</p>`;
        tasksPaginationDiv.classList.add('d-none');
        return;
    }
    
    // Calculate pagination
    const startIndex = tasksCurrentPage * tasksPageSize;
    const endIndex = Math.min(startIndex + tasksPageSize, filteredTasksData.length);
    const currentPageTasks = filteredTasksData.slice(startIndex, endIndex);
    
    // Update pagination info
    document.getElementById('tasksStartIndex').textContent = startIndex + 1;
    document.getElementById('tasksEndIndex').textContent = endIndex;
    document.getElementById('tasksTotalCount').textContent = tasksTotalCount;
    
    const totalPages = Math.ceil(tasksTotalCount / tasksPageSize);
    document.getElementById('tasksPageInfo').textContent = `Page ${tasksCurrentPage + 1} of ${totalPages}`;
    
    // Update pagination buttons
    document.getElementById('tasksPrevBtn').disabled = tasksCurrentPage === 0;
    document.getElementById('tasksNextBtn').disabled = tasksCurrentPage >= totalPages - 1;
    
    // Show pagination if there are more than pageSize tasks
    if (tasksTotalCount > tasksPageSize) {
        tasksPaginationDiv.classList.remove('d-none');
    } else {
        tasksPaginationDiv.classList.add('d-none');
    }

    let html = `<div class="table-responsive"><table class="table table-sm align-middle">
        <thead>
            <tr>
                <th>Title</th>
                <th>Parent</th>
                <th>Progress</th>
                <th>Deadline</th>
            </tr>
        </thead>
        <tbody>`;
    currentPageTasks.forEach(task => {
        const project = projectsData.find(p => Number(p.id) === Number(task.proj_id));
        const projectName = project ? project.name : 'Unknown Project';
        const parentTask = task.parent_task_id ? tasksData.find(t => Number(t.id) === Number(task.parent_task_id)) : null;
        const parentInfo = parentTask ? `<span class="badge rounded-pill bg-info text-dark">${parentTask.title}</span>` : '';
        const progressPercentage = task.progress && task.progress.max_value > 0 
            ? Math.round((task.progress.value / task.progress.max_value) * 100) 
            : 0;
        html += `
            <tr>
                <td class="fw-bold">
                    <span style='cursor:pointer;' onclick='editTask(${task.id})' title='Edit Task'>${task.title}</span>
                    <div style='font-weight:normal; margin-top:2px;'>
                        <div style="display: flex; flex-wrap: wrap; gap: 4px; align-items: center;">
                            <span class="badge bg-${task.state === 'done' ? 'success' : task.state === 'doing' ? 'warning' : 'secondary'}">${task.state.toUpperCase()}</span>
                            <span class="badge bg-${task.energy_level === 'HIGH' ? 'danger' : task.energy_level === 'MEDIUM' ? 'warning' : 'success'}">${task.energy_level} Energy</span>
                            ${task.is_important ? '<span class="badge bg-danger">Important</span>' : ''}
                            ${task.is_urgent ? '<span class="badge bg-warning">Urgent</span>' : ''}
                            ${project ? `<span class="badge" style="background:${project.color};color:${getContrastYIQ(project.color)};">${projectName}</span>` : ''}
                        </div>
                    </div>
                </td>
                <td>${parentInfo}</td>
                <td>
                    ${task.progress ? `<div class='progress' style='height: 18px; cursor:pointer;' onclick='editProgress(${task.id}, ${task.progress_id})' title='Edit Progress'><div class='progress-bar bg-info' role='progressbar' style='width: ${progressPercentage}%' aria-valuenow='${progressPercentage}' aria-valuemin='0' aria-valuemax='100'>${progressPercentage}%</div></div>` : ''}
                </td>
                <td>${task.deadline ? `<span class=\"text-muted\"><i class=\"bi bi-calendar-event me-1\"></i>${new Date(task.deadline).toLocaleDateString()}</span>` : ''}</td>
                <td class="text-center">
                    <input type="checkbox" class="form-check-input" onchange="if(this.checked){closeTask(${task.id})}\" title="Close Task" />
                </td>
            </tr>
        `;
    });
    html += '</tbody></table></div>';
    tasksListDiv.innerHTML = html;
}

// Task filtering and pagination functions
function applyTaskFiltersToData(tasks) {
    return tasks.filter(task => {
        // State filter
        if (taskFilters.state && task.state !== taskFilters.state) {
            return false;
        }
        
        // Project filter
        if (taskFilters.project && Number(task.proj_id) !== Number(taskFilters.project)) {
            return false;
        }
        
        // Energy level filter
        if (taskFilters.energy && task.energy_level !== taskFilters.energy) {
            return false;
        }
        
        // Importance filter
        if (taskFilters.importance === 'important' && !task.is_important) {
            return false;
        }
        if (taskFilters.importance === 'not_important' && task.is_important) {
            return false;
        }
        
        // Urgency filter
        if (taskFilters.urgency === 'urgent' && !task.is_urgent) {
            return false;
        }
        if (taskFilters.urgency === 'not_urgent' && task.is_urgent) {
            return false;
        }
        
        // Deadline filter
        if (taskFilters.deadline) {
            if (!task.deadline) return false;
            const now = new Date();
            const taskDeadline = new Date(task.deadline);
            const filterDeadline = new Date(taskFilters.deadline);
            if (taskDeadline < now || taskDeadline > filterDeadline) {
                return false;
            }
        }
        
        // Parent task filter
        if (taskFilters.parent) {
            if (taskFilters.parent === 'no_parent') {
                // Show only tasks with no parent
                if (task.parent_task_id) return false;
            } else {
                // Show only tasks with specific parent
                if (Number(task.parent_task_id) !== Number(taskFilters.parent)) return false;
            }
        }
        
        return true;
    });
}

async function applyTaskFilters() {
    // Get filter values
    taskFilters.state = document.getElementById('stateFilter').value;
    taskFilters.project = document.getElementById('projectFilter').value;
    taskFilters.energy = document.getElementById('energyFilter').value;
    taskFilters.importance = document.getElementById('importanceFilter').value;
    taskFilters.urgency = document.getElementById('urgencyFilter').value;
    taskFilters.deadline = document.getElementById('deadlineFilterDate').value;
    taskFilters.parent = document.getElementById('parentTaskFilter').value;
    
    // Reset to first page
    tasksCurrentPage = 0;
    
    // Always load all tasks, then filter on frontend
    await loadAllTasks();
    displayTasksList();
}

async function clearTaskFilters() {
    // Clear all filter inputs
    document.getElementById('stateFilter').value = '';
    document.getElementById('projectFilter').value = '';
    document.getElementById('energyFilter').value = '';
    document.getElementById('importanceFilter').value = '';
    document.getElementById('urgencyFilter').value = '';
    document.getElementById('deadlineFilterDate').value = '';
    document.getElementById('parentTaskFilter').value = '';
    
    // Clear filter object
    taskFilters = {
        state: '',
        project: '',
        energy: '',
        importance: '',
        urgency: '',
        deadline: '',
        parent: ''
    };
    
    // Reset to first page
    tasksCurrentPage = 0;
    
    // Load all tasks
    await loadAllTasks();
    displayTasksList();
}

function tasksPreviousPage() {
    if (tasksCurrentPage > 0) {
        tasksCurrentPage--;
        displayTasksList();
    }
}

function tasksNextPage() {
    const totalPages = Math.ceil(tasksTotalCount / tasksPageSize);
    if (tasksCurrentPage < totalPages - 1) {
        tasksCurrentPage++;
        displayTasksList();
    }
}

function populateTaskFilters() {
    // Populate project filter
    const projectFilter = document.getElementById('projectFilter');
    const currentProjectValue = projectFilter.value; // Preserve current selection
    
    projectFilter.innerHTML = '<option value="">All Projects</option>';
    projectsData.forEach(project => {
        projectFilter.innerHTML += `<option value="${project.id}">${project.name}</option>`;
    });
    
    // Restore the previous selection if it exists
    if (currentProjectValue) {
        projectFilter.value = currentProjectValue;
    }
    
    // Add event listener for project filter (only if not already added)
    if (!projectFilter.hasAttribute('data-listener-added')) {
        projectFilter.addEventListener('change', async function() {
            await loadAllTasks();
            displayTasksList();
            populateParentTaskFilter(); // Repopulate parent task filter when project changes
        });
        projectFilter.setAttribute('data-listener-added', 'true');
    }
    
    // Populate parent task filter
    populateParentTaskFilter();
}

function populateParentTaskFilter() {
    const parentTaskFilter = document.getElementById('parentTaskFilter');
    const currentParentValue = parentTaskFilter.value; // Preserve current selection
    const projectFilter = document.getElementById('projectFilter');
    const selectedProjectId = projectFilter ? projectFilter.value : '';

    parentTaskFilter.innerHTML = '<option value="">All Tasks</option><option value="no_parent">No Parent (Top Level)</option>';
    let filteredTasks = tasksData;
    if (selectedProjectId) {
        filteredTasks = tasksData.filter(task => String(task.proj_id) === String(selectedProjectId));
    }
    filteredTasks.forEach(task => {
        parentTaskFilter.innerHTML += `<option value="${task.id}">${task.title}</option>`;
    });

    // Restore the previous selection if it exists
    if (currentParentValue) {
        parentTaskFilter.value = currentParentValue;
    }
}

// Model Management Functions
function showCreateModelForm() {
    document.getElementById('createModelForm').style.display = 'block';
    document.getElementById('modelsList').style.display = 'none';
}

function hideCreateModelForm() {
    document.getElementById('createModelForm').style.display = 'none';
    document.getElementById('modelsList').style.display = 'block';
    document.getElementById('newModelForm').reset();
}

// Model Edit/Delete Functions
async function editModel(apiKey) {
    try {
        const userApiKey = localStorage.getItem('apiKey');
        if (!userApiKey) {
            showToast('error', 'Error', 'No API key found. Please log in again.');
            window.location.href = '/login';
            return;
        }
        // Fetch the model data by API key
        const response = await fetch(`/models/${apiKey}`, {
            headers: {
                'X-API-Key': userApiKey
            }
        });
        if (response.ok) {
            const model = await response.json();
            document.getElementById('editModelId').value = model.api_key;
            document.getElementById('editModelName').value = model.name;
            document.getElementById('editModelBaseUrl').value = model.base_url;
            const modal = new bootstrap.Modal(document.getElementById('editModelModal'));
            modal.show();
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to load model: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error loading model for edit:', error);
        showToast('error', 'Error', `Error loading model: ${error.message}`);
    }
}

document.getElementById('updateModelBtn').addEventListener('click', async function() {
    const apiKey = document.getElementById('editModelId').value;
    const name = document.getElementById('editModelName').value;
    const base_url = document.getElementById('editModelBaseUrl').value;
    if (!name || !base_url) {
        showToast('warning', 'Validation Error', 'Please fill in all required fields');
        return;
    }
    try {
        const userApiKey = localStorage.getItem('apiKey');
        const response = await fetch(`/models/${apiKey}`, {
            method: 'PUT',
            headers: {
                'X-API-Key': userApiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name, base_url })
        });
        if (response.ok) {
            const modal = bootstrap.Modal.getInstance(document.getElementById('editModelModal'));
            modal.hide();
            await loadModels();
            showToast('success', 'Success!', 'Model updated successfully!');
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to update model: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error updating model:', error);
        showToast('error', 'Error', `Error updating model: ${error.message}`);
    }
});

async function deleteModel(apiKey) {
    // Show confirmation modal instead of alert
    const confirmModal = new bootstrap.Modal(document.getElementById('confirmDeleteModal'));
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    const cancelBtn = document.getElementById('cancelDeleteBtn');
    const modalBody = document.getElementById('confirmDeleteBody');
    
    modalBody.textContent = 'Are you sure you want to delete this model? This action cannot be undone.';
    
    // Set up confirmation handler
    const handleConfirm = async () => {
        confirmModal.hide();
        await performModelDeletion(apiKey);
        // Clean up event listeners
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', handleCancel);
    };
    
    const handleCancel = () => {
        confirmModal.hide();
        // Clean up event listeners
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', handleCancel);
    };
    
    confirmBtn.addEventListener('click', handleConfirm);
    cancelBtn.addEventListener('click', handleCancel);
    
    confirmModal.show();
}

// Perform the actual model deletion
async function performModelDeletion(apiKey) {
    try {
        const userApiKey = localStorage.getItem('apiKey');
        const response = await fetch(`/models/${apiKey}`, {
            method: 'DELETE',
            headers: {
                'X-API-Key': userApiKey
            }
        });

        if (response.ok) {
            showToast('success', 'Success!', 'Model deleted successfully!');
            await loadModels();
        } else {
            // Try to parse JSON error response
            let errorMessage = 'Unknown error';
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || 'Unknown error';
            } catch (parseError) {
                // If JSON parsing fails, get the text response
                const textResponse = await response.text();
                console.error('Non-JSON response:', textResponse);
                errorMessage = `Server error (${response.status}): ${textResponse.substring(0, 100)}`;
            }
            showToast('error', 'Error', `Failed to delete model: ${errorMessage}`);
        }
    } catch (error) {
        console.error('Error deleting model:', error);
        showToast('error', 'Error', `Error deleting model: ${error.message}`);
    }
}

// Project Management Functions
function showCreateProjectForm() {
    document.getElementById('createProjectForm').style.display = 'block';
    document.getElementById('projectsList').style.display = 'none';
}

function hideCreateProjectForm() {
    document.getElementById('createProjectForm').style.display = 'none';
    document.getElementById('projectsList').style.display = 'block';
    document.getElementById('newProjectForm').reset();
}

// Task Management Functions
async function showCreateTaskForm() {
    console.log('showCreateTaskForm called');
    document.getElementById('createTaskForm').style.display = 'block';
    document.getElementById('tasksList').style.display = 'none';
    
    // Ensure both tasks and projects are loaded when opening the modal
    console.log('Loading tasks and projects...');
    await loadAllTasks();
    await loadProjects();
    console.log('Tasks and projects loaded, now displaying tasks list');
    // displayTasksList() will be called by populateProjectSelects() after projects are loaded
}

function hideCreateTaskForm() {
    document.getElementById('createTaskForm').style.display = 'none';
    document.getElementById('tasksList').style.display = 'block';
    document.getElementById('newTaskForm').reset();
}

// Project Edit/Delete Functions
async function editProject(projectId) {
    const project = projectsData.find(p => Number(p.id) === Number(projectId));
    if (!project) {
        showToast('error', 'Error', 'Project not found');
        return;
    }
    document.getElementById('editProjectId').value = project.id;
    document.getElementById('editProjectName').value = project.name;
    document.getElementById('editProjectColor').value = project.color;
    const modal = new bootstrap.Modal(document.getElementById('editProjectModal'));
    modal.show();
}

document.getElementById('updateProjectBtn').addEventListener('click', async function() {
    const id = document.getElementById('editProjectId').value;
    const name = document.getElementById('editProjectName').value;
    const color = document.getElementById('editProjectColor').value;
    if (!name || !color) {
        showToast('warning', 'Validation Error', 'Please fill in all required fields');
        return;
    }
    try {
        const apiKey = localStorage.getItem('apiKey');
        const response = await fetch(`/projects/${id}`, {
            method: 'PUT',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name, color })
        });
        if (response.ok) {
            const modal = bootstrap.Modal.getInstance(document.getElementById('editProjectModal'));
            modal.hide();
            await loadProjects();
            showToast('success', 'Success!', 'Project updated successfully!');
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to update project: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error updating project:', error);
        showToast('error', 'Error', `Error updating project: ${error.message}`);
    }
});

async function deleteProject(projectId) {
    // Show confirmation modal instead of alert
    const confirmModal = new bootstrap.Modal(document.getElementById('confirmDeleteModal'));
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    const cancelBtn = document.getElementById('cancelDeleteBtn');
    const modalBody = document.getElementById('confirmDeleteBody');
    
    modalBody.textContent = 'Are you sure you want to delete this project? This action cannot be undone.';
    
    // Set up confirmation handler
    const handleConfirm = async () => {
        confirmModal.hide();
        await performProjectDeletion(projectId);
        // Clean up event listeners
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', handleCancel);
    };
    
    const handleCancel = () => {
        confirmModal.hide();
        // Clean up event listeners
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', handleCancel);
    };
    
    confirmBtn.addEventListener('click', handleConfirm);
    cancelBtn.addEventListener('click', handleCancel);
    
    confirmModal.show();
}

// Perform the actual project deletion
async function performProjectDeletion(projectId) {

    try {
        const apiKey = localStorage.getItem('apiKey');
        const response = await fetch(`/projects/${projectId}`, {
            method: 'DELETE',
            headers: {
                'X-API-Key': apiKey
            }
        });

        if (response.ok) {
            showToast('success', 'Success!', 'Project deleted successfully!');
            await loadProjects();
            // Refresh dashboard data without page reload
            await refreshDashboardData();
        } else {
            // Try to parse JSON error response
            let errorMessage = 'Unknown error';
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || 'Unknown error';
            } catch (parseError) {
                // If JSON parsing fails, get the text response
                const textResponse = await response.text();
                console.error('Non-JSON response:', textResponse);
                errorMessage = `Server error (${response.status}): ${textResponse.substring(0, 100)}`;
            }
            showToast('error', 'Error', `Failed to delete project: ${errorMessage}`);
        }
    } catch (error) {
        console.error('Error deleting project:', error);
        showToast('error', 'Error', `Error deleting project: ${error.message}`);
    }
}

// Task Edit/Delete Functions
async function editTask(taskId) {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
            showToast('error', 'Error', 'No API key found. Please log in again.');
            window.location.href = '/login';
            return;
        }
        // Fetch the task data
        const response = await fetch(`/tasks/${taskId}`, {
            headers: {
                'X-API-Key': apiKey
            }
        });
        if (response.ok) {
            const task = await response.json();
            // Populate project select for edit modal first
            populateEditProjectSelect();
            const projectSelect = document.getElementById('editTaskProject');
            // Ensure the project is present in the select
            let found = false;
            for (let i = 0; i < projectSelect.options.length; i++) {
                if (String(projectSelect.options[i].value).trim() === String(task.proj_id).trim()) {
                    found = true;
                    break;
                }
            }
            if (!found && task.proj_id) {
                const opt = document.createElement('option');
                opt.value = String(task.proj_id).trim();
                opt.textContent = `Project ${task.proj_id}`;
                projectSelect.appendChild(opt);
            }
            // Debug: log options and value being set
            console.log('Setting project select value:', task.proj_id, 'Options:', Array.from(projectSelect.options).map(o => o.value));
            // Set value after a short delay to ensure select is ready
            setTimeout(() => {
                projectSelect.value = String(task.proj_id).trim();
                projectSelect.dispatchEvent(new Event('change'));
            }, 50);
            document.getElementById('editTaskId').value = task.id;
            document.getElementById('editTaskTitle').value = task.title;
            document.getElementById('editTaskParent').value = task.parent_task_id || '';
            document.getElementById('editTaskEnergy').value = task.energy_level;
            document.getElementById('editTaskState').value = task.state;
            document.getElementById('editTaskImportant').checked = task.is_important;
            document.getElementById('editTaskUrgent').checked = task.is_urgent;
            
            if (task.deadline) {
                const deadline = new Date(task.deadline);
                const deadlineFormatted = formatDateTimeForInput(deadline);
                document.getElementById('editTaskDeadline').value = deadlineFormatted;
            } else {
                document.getElementById('editTaskDeadline').value = '';
            }
            
            // Populate project select for edit modal
            populateEditProjectSelect();
            
            // Set the href for the See Notes button with the actual task ID
            const seeNotesBtn = document.getElementById('seeNotesBtn');
            if (seeNotesBtn) {
                seeNotesBtn.href = `/notes/timeline?task_id=${taskId}`;
                console.log(`Set See Notes button href to: /notes/timeline?task_id=${taskId}`);
            }
            
            const modal = new bootstrap.Modal(document.getElementById('editTaskModal'));
            modal.show();
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to load task: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error loading task for edit:', error);
        showToast('error', 'Error', `Error loading task: ${error.message}`);
    }
}

function populateEditProjectSelect() {
    const select = document.getElementById('editTaskProject');
    select.innerHTML = '<option value="">Select project...</option>';
    projectsData.forEach(project => {
        const option = document.createElement('option');
        option.value = project.id;
        option.textContent = project.name;
        select.appendChild(option);
    });
}

document.getElementById('updateTaskBtn').addEventListener('click', async function() {
    const taskId = document.getElementById('editTaskId').value;
    const title = document.getElementById('editTaskTitle').value;
    const projectId = document.getElementById('editTaskProject').value;
    const parentTaskId = document.getElementById('editTaskParent').value;
    const energy = document.getElementById('editTaskEnergy').value;
    const state = document.getElementById('editTaskState').value;
    const isImportant = document.getElementById('editTaskImportant').checked;
    const isUrgent = document.getElementById('editTaskUrgent').checked;
    const deadline = document.getElementById('editTaskDeadline').value;

    if (!title || !projectId || !energy || !state) {
        showToast('warning', 'Validation Error', 'Please fill in all required fields');
        return;
    }

    try {
        const apiKey = localStorage.getItem('apiKey');
        const updateData = {
            title: title,
            proj_id: parseInt(projectId),
            energy_level: energy,
            state: state,
            is_important: isImportant,
            is_urgent: isUrgent
        };

        if (parentTaskId) {
            updateData.parent_task_id = parseInt(parentTaskId);
        } else {
            updateData.parent_task_id = null;
        }

        if (deadline) {
            updateData.deadline = new Date(deadline).toISOString();
        }

        const response = await fetch(`/tasks/${taskId}`, {
            method: 'PUT',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updateData)
        });

        if (response.ok) {
            const modal = bootstrap.Modal.getInstance(document.getElementById('editTaskModal'));
            modal.hide();
            await loadAllTasks();
            showToast('success', 'Success!', 'Task updated successfully!');
            // Refresh dashboard data without page reload
            await refreshDashboardData();
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to update task: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error updating task:', error);
        showToast('error', 'Error', `Error updating task: ${error.message}`);
    }
});

// Progress Edit Function
async function editProgress(taskId, progressId) {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
            showToast('error', 'Error', 'No API key found. Please log in again.');
            window.location.href = '/login';
            return;
        }

        // Fetch the progress data
        const response = await fetch(`/progress/${progressId}`, {
            headers: {
                'X-API-Key': apiKey
            }
        });

        if (response.ok) {
            const progress = await response.json();
            
            // Populate the edit form
            document.getElementById('editProgressId').value = progress.id;
            document.getElementById('editProgressTaskId').value = taskId;
            document.getElementById('editProgressUnit').value = progress.unit;
            document.getElementById('editProgressValue').value = progress.value;
            document.getElementById('editProgressMax').value = progress.max_value;
            
            // Update progress bar
            updateProgressBar(progress.value, progress.max_value);
            
            // Show the modal
            const modal = new bootstrap.Modal(document.getElementById('progressEditModal'));
            modal.show();
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to load progress: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error loading progress for edit:', error);
        showToast('error', 'Error', `Error loading progress: ${error.message}`);
    }
}

// Update progress bar display
function updateProgressBar(value, maxValue) {
    const percentage = maxValue > 0 ? Math.round((value / maxValue) * 100) : 0;
    const progressBar = document.getElementById('editProgressBar');
    const progressText = document.getElementById('editProgressText');
    
    progressBar.style.width = `${percentage}%`;
    progressText.textContent = `${percentage}%`;
    
    // Update color based on percentage
    if (percentage >= 100) {
        progressBar.className = 'progress-bar bg-success';
    } else if (percentage >= 75) {
        progressBar.className = 'progress-bar bg-info';
    } else if (percentage >= 50) {
        progressBar.className = 'progress-bar bg-warning';
    } else {
        progressBar.className = 'progress-bar bg-secondary';
    }
}

// Progress Update Event Listener
document.getElementById('updateProgressBtn').addEventListener('click', async function() {
    const progressId = document.getElementById('editProgressId').value;
    const taskId = document.getElementById('editProgressTaskId').value;
    const value = parseInt(document.getElementById('editProgressValue').value);
    const maxValue = parseInt(document.getElementById('editProgressMax').value);

    if (isNaN(value) || value < 0) {
        showToast('warning', 'Validation Error', 'Please enter a valid progress value');
        return;
    }

    if (value > maxValue) {
        showToast('warning', 'Validation Error', 'Progress value cannot exceed maximum value');
        return;
    }

    try {
        const apiKey = localStorage.getItem('apiKey');
        const updateData = {
            value: value
        };

        const response = await fetch(`/progress/${progressId}`, {
            method: 'PUT',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updateData)
        });

        if (response.ok) {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('progressEditModal'));
            modal.hide();
            
            // Reset form
            document.getElementById('progressEditForm').reset();
            
            // Reload tasks to show updated progress
            await loadAllTasks();
            
            showToast('success', 'Success!', 'Progress updated successfully!');
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to update progress: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error updating progress:', error);
        showToast('error', 'Error', `Error updating progress: ${error.message}`);
    }
});

// Real-time progress bar updates
document.getElementById('editProgressValue').addEventListener('input', function() {
    const value = parseInt(this.value) || 0;
    const maxValue = parseInt(document.getElementById('editProgressMax').value) || 1;
    updateProgressBar(value, maxValue);
});

async function closeTask(taskId) {
    try {
        const apiKey = localStorage.getItem('apiKey');
        const response = await fetch(`/tasks/${taskId}`, {
            method: 'PUT',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ state: 'closed' })
        });
        if (response.ok) {
            showToast('success', 'Task Closed', 'Task marked as closed!');
            await loadAllTasks();
            await refreshDashboardData();
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to close task: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error closing task:', error);
        showToast('error', 'Error', `Error closing task: ${error.message}`);
    }
}

// Logout Function
function logout() {
    // Show confirmation modal instead of alert
    const confirmModal = new bootstrap.Modal(document.getElementById('confirmDeleteModal'));
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    const cancelBtn = document.getElementById('cancelDeleteBtn');
    const modalBody = document.getElementById('confirmDeleteBody');
    
    modalBody.textContent = 'Are you sure you want to logout?';
    
    // Change button text for logout
    confirmBtn.innerHTML = '<i class="bi bi-box-arrow-right me-2"></i>Logout';
    
    // Set up confirmation handler
    const handleConfirm = () => {
        confirmModal.hide();
        // Clear all stored data
        localStorage.removeItem('apiKey');
        localStorage.removeItem('userId');
        localStorage.removeItem('username');
        localStorage.removeItem('displayName');
        
        // Redirect to landing page
        window.location.href = '/';
        // Clean up event listeners
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', handleCancel);
    };
    
    const handleCancel = () => {
        confirmModal.hide();
        // Reset button text back to "Delete" for other uses
        confirmBtn.innerHTML = '<i class="bi bi-trash me-2"></i>Delete';
        // Clean up event listeners
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', handleCancel);
    };
    
    confirmBtn.addEventListener('click', handleConfirm);
    cancelBtn.addEventListener('click', handleCancel);
    
    confirmModal.show();
}

// Edit Activity Function
async function editActivity(activityId) {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
            alert('No API key found. Please log in again.');
            window.location.href = '/login';
            return;
        }

        const response = await fetch(`/activities/${activityId}`, {
            headers: {
                'X-API-Key': apiKey
            }
        });

        if (response.ok) {
            const activity = await response.json();
            document.getElementById('editActivityId').value = activity.id;
            document.getElementById('editActivityStatus').value = activity.status;

            // Find the task to get its project (try tasksData, then taskCache)
            let task = tasksData.find(t => t.id == activity.task_id);
            if (!task && taskCache[activity.task_id]) task = taskCache[activity.task_id];
            if (task) {
                // Always populate the project dropdown
                populateEditActivityProjectSelect();
                document.getElementById('editActivityProject').value = task.proj_id;
                // Repopulate tasks for that project
                populateEditActivityTasks();
                // Ensure the task is present in the select, add if missing
                const taskSelect = document.getElementById('editActivityTask');
                let found = false;
                for (let i = 0; i < taskSelect.options.length; i++) {
                    if (String(taskSelect.options[i].value) === String(activity.task_id)) {
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    // Add the missing task as a temporary option
                    const opt = document.createElement('option');
                    opt.value = String(activity.task_id);
                    opt.textContent = task.title + ' (archived or unavailable)';
                    taskSelect.appendChild(opt);
                }
                taskSelect.value = String(activity.task_id);
            } else {
                // Fallback: just populate selects
                populateEditActivityProjectSelect();
                populateEditActivityTasks();
            }

            // Format datetime for input fields - convert to local timezone
            const clockIn = new Date(activity.clock_in);
            const clockInFormatted = formatDateTimeForInput(clockIn);
            document.getElementById('editActivityClockIn').value = clockInFormatted;

            if (activity.clock_out) {
                const clockOut = new Date(activity.clock_out);
                const clockOutFormatted = formatDateTimeForInput(clockOut);
                document.getElementById('editActivityClockOut').value = clockOutFormatted;
            } else {
                document.getElementById('editActivityClockOut').value = '';
            }

            document.getElementById('editActivityDescription').value = activity.description || '';

            const modal = new bootstrap.Modal(document.getElementById('editActivityModal'));
            modal.show();
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to load activity: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error loading activity for edit:', error);
        showToast('error', 'Error', `Error loading activity: ${error.message}`);
    }
}

// Helper function to format datetime for input fields
function formatDateTimeForInput(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function populateEditTaskSelect() {
    const select = document.getElementById('editActivityTask');
    select.innerHTML = '<option value="">Choose a task...</option>';
    
    // Get the current activity's task ID from the hidden field
    const activityId = document.getElementById('editActivityId').value;
    const currentTaskId = document.getElementById('editActivityTask').value;
    
    // Filter out tasks that are done or closed, but include the current task
    const availableTasks = tasksData.filter(task => {
        if (currentTaskId && Number(task.id) === Number(currentTaskId)) {
            return true;
        }
        return task.state !== 'done' && task.state !== 'closed';
    });
    
    console.log('Available tasks for activity editing:', availableTasks.length, 'out of', tasksData.length, 'total tasks');
    console.log('Current task ID:', currentTaskId);
    
    availableTasks.forEach(task => {
        const option = document.createElement('option');
        option.value = task.id;
        option.textContent = task.title;
        select.appendChild(option);
        console.log('Added task option for editing:', task.id, task.title, '(state:', task.state, ')');
    });
}

// Delete Activity Function
async function deleteActivity(activityId) {
    // Show confirmation modal instead of alert
    const confirmModal = new bootstrap.Modal(document.getElementById('confirmDeleteModal'));
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    const cancelBtn = document.getElementById('cancelDeleteBtn');
    const modalBody = document.getElementById('confirmDeleteBody');
    
    modalBody.textContent = 'Are you sure you want to delete this activity? This action cannot be undone.';
    
    // Set up confirmation handler
    const handleConfirm = async () => {
        confirmModal.hide();
        await performActivityDeletion(activityId);
        // Clean up event listeners
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', handleCancel);
    };
    
    const handleCancel = () => {
        confirmModal.hide();
        // Clean up event listeners
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', handleCancel);
    };
    
    confirmBtn.addEventListener('click', handleConfirm);
    cancelBtn.addEventListener('click', handleCancel);
    
    confirmModal.show();
}

// Perform the actual deletion
async function performActivityDeletion(activityId) {

    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
            alert('No API key found. Please log in again.');
            window.location.href = '/login';
            return;
        }

        const response = await fetch(`/activities/${activityId}`, {
            method: 'DELETE',
            headers: {
                'X-API-Key': apiKey
            }
        });

        if (response.ok) {
            // Reload the schedule to reflect the deletion
            await loadActivitiesWithPagination();
            showToast('success', 'Success!', 'Activity deleted successfully!');
            // Refresh dashboard data without page reload
            await refreshDashboardData();
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to delete activity: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error deleting activity:', error);
        showToast('error', 'Error', `Error deleting activity: ${error.message}`);
    }
}

// Update Activity Event Listener
document.getElementById('updateActivityBtn').addEventListener('click', async function() {
    const activityId = document.getElementById('editActivityId').value;
    const projectId = document.getElementById('editActivityProject').value;
    const taskId = document.getElementById('editActivityTask').value;
    const status = document.getElementById('editActivityStatus').value;
    const clockIn = document.getElementById('editActivityClockIn').value;
    const clockOut = document.getElementById('editActivityClockOut').value;
    const description = document.getElementById('editActivityDescription').value;

    if (!projectId || !taskId || !clockIn) {
        showToast('warning', 'Validation Error', 'Please fill in all required fields');
        return;
    }

    // Validate that a project is selected
    if (projectId === '') {
        showToast('warning', 'Validation Error', 'Please select a project');
        return;
    }

    // Validate that a task is selected
    if (taskId === '') {
        showToast('warning', 'Validation Error', 'Please select a task');
        return;
    }

    try {
        const apiKey = localStorage.getItem('apiKey');
        const updateData = {
            task_id: parseInt(taskId),
            status: status,
            clock_in: new Date(clockIn).toISOString(),
            description: description || null
        };

        if (clockOut) {
            updateData.clock_out = new Date(clockOut).toISOString();
        }

        const response = await fetch(`/activities/${activityId}`, {
            method: 'PUT',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updateData)
        });

        if (response.ok) {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('editActivityModal'));
            modal.hide();
            
            // Reset form
            document.getElementById('editActivityForm').reset();
            
            // Reload schedule
            await loadActivitiesWithPagination();
            
            showToast('success', 'Success!', 'Activity updated successfully!');
            // Refresh dashboard data without page reload
            await refreshDashboardData();
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to update activity: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error updating activity:', error);
        showToast('error', 'Error', `Error updating activity: ${error.message}`);
    }
});

// Model Form Submission
document.getElementById('newModelForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const name = document.getElementById('modelName').value;
    const baseUrl = document.getElementById('modelBaseUrl').value;
    const apiKey = document.getElementById('modelApiKey').value;

    if (!name || !baseUrl || !apiKey) {
        showToast('warning', 'Validation Error', 'Please fill in all required fields');
        return;
    }

    try {
        const userApiKey = localStorage.getItem('apiKey');
        const response = await fetch('/models/', {
            method: 'POST',
            headers: {
                'X-API-Key': userApiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                base_url: baseUrl,
                api_key: apiKey
            })
        });

        if (response.ok) {
            showToast('success', 'Success!', 'Model created successfully!');
            hideCreateModelForm();
            await loadModels();
            // Refresh dashboard data without page reload
            await refreshDashboardData();
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to create model: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error creating model:', error);
        showToast('error', 'Error', `Error creating model: ${error.message}`);
    }
});

// Project Form Submission
document.getElementById('newProjectForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const name = document.getElementById('projectName').value;
    const color = document.getElementById('projectColor').value;

    if (!name || !color) {
        showToast('warning', 'Validation Error', 'Please fill in all required fields');
        return;
    }

    console.log('Creating project with data:', { name, color });

    try {
        const apiKey = localStorage.getItem('apiKey');
        const projectData = {
            name: name,
            color: color
        };

        console.log('Sending project data:', projectData);

        const response = await fetch('/projects/', {
            method: 'POST',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(projectData)
        });

        console.log('Project creation response status:', response.status);

        if (response.ok) {
            const createdProject = await response.json();
            console.log('Project created successfully:', createdProject);
            showToast('success', 'Success!', 'Project created successfully!');
            hideCreateProjectForm();
            await loadProjects();
            await loadAllTasks(); // Reload tasks to update project options
            // Refresh dashboard data without page reload
            await refreshDashboardData();
        } else {
            const errorData = await response.json();
            console.error('Failed to create project:', errorData);
            showToast('error', 'Error', `Failed to create project: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error creating project:', error);
        showToast('error', 'Error', `Error creating project: ${error.message}`);
    }
});

// Handle project selection for parent task dropdown
document.getElementById('taskProject').addEventListener('change', function() {
    const selectedProjectId = this.value;
    const parentTaskSelect = document.getElementById('taskParent');
    
    // Clear existing options except the first one
    parentTaskSelect.innerHTML = '<option value="">No Parent (Top Level Task)</option>';
    
    if (selectedProjectId) {
        // Filter tasks for the selected project
        const projectTasks = tasksData.filter(task => 
            Number(task.proj_id) === Number(selectedProjectId) && 
            task.state !== 'done' && 
            task.state !== 'closed'
        );
        
        // Add available parent tasks
        projectTasks.forEach(task => {
            const option = document.createElement('option');
            option.value = task.id;
            option.textContent = task.title;
            parentTaskSelect.appendChild(option);
        });
        
        console.log(`Found ${projectTasks.length} available parent tasks for project ${selectedProjectId}`);
    }
});

// Function to refresh all dashboard data without page reload
async function refreshDashboardData() {
    try {
        console.log('Refreshing dashboard data...');

        // Helper to wrap each loader with logging and error catching
        async function logAndRun(name, fn) {
            try {
                console.log(`[refreshDashboardData] Starting: ${name}`);
                const result = await fn();
                console.log(`[refreshDashboardData] Success: ${name}`);
                return result;
            } catch (err) {
                console.error(`[refreshDashboardData] Error in ${name}:`, err);
                throw new Error(`${name} failed: ${err && err.message ? err.message : err}`);
            }
        }

        // Run all loaders in parallel, but with individual logging
        await Promise.all([
            logAndRun('loadAllTasks', loadAllTasks),
            logAndRun('loadProjects', loadProjects),
            logAndRun('loadModels', loadModels),
            logAndRun('loadActivitiesWithPagination', loadActivitiesWithPagination),
            logAndRun('loadCalendarActivities', loadCalendarActivities),
            logAndRun('loadReminders', loadReminders)
        ]);

        // Update UI components that depend on the refreshed data
        document.getElementById('scheduleTitle').textContent = "Today's Schedule";
        setCurrentDoingActivityFromSchedule();
        enableActivityButtons();
        loadUpcomingActivities();

        console.log('Dashboard data refreshed successfully');
    } catch (error) {
        console.error('Error refreshing dashboard data:', error);
        showToast('error', 'Error', `Failed to refresh dashboard data: ${error && error.message ? error.message : error}`);
    }
}

// Task Form Submission
document.getElementById('newTaskForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const title = document.getElementById('taskTitle').value;
    const projectId = document.getElementById('taskProject').value;
    const parentTaskId = document.getElementById('taskParent').value;
    const energy = document.getElementById('taskEnergy').value;
    const state = document.getElementById('taskState').value;
    const isImportant = document.getElementById('taskImportant').checked;
    const isUrgent = document.getElementById('taskUrgent').checked;
    const deadline = document.getElementById('taskDeadline').value;
    const progressUnit = document.getElementById('taskProgressUnit').value;
    const progressValue = parseInt(document.getElementById('taskProgressValue').value);
    const progressMax = parseInt(document.getElementById('taskProgressMax').value);

    if (!title || !projectId || !energy || !state || !progressUnit) {
        showToast('warning', 'Validation Error', 'Please fill in all required fields');
        return;
    }

    if (progressValue < 0 || progressMax <= 0) {
        showToast('warning', 'Validation Error', 'Progress values must be valid (current ≥ 0, max > 0)');
        return;
    }

    if (progressValue > progressMax) {
        showToast('warning', 'Validation Error', 'Current progress cannot exceed maximum value');
        return;
    }

    try {
        const apiKey = localStorage.getItem('apiKey');
        
        // First, create a progress record
        const progressData = {
            unit: progressUnit,
            value: progressValue,
            max_value: progressMax
        };

        console.log('Creating progress with data:', progressData);

        const progressResponse = await fetch('/progress/', {
            method: 'POST',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(progressData)
        });

        if (!progressResponse.ok) {
            const errorData = await progressResponse.json();
            showToast('error', 'Error', `Failed to create progress: ${errorData.detail || 'Unknown error'}`);
            return;
        }

        const createdProgress = await progressResponse.json();
        console.log('Progress created successfully:', createdProgress);

        // Now create the task with the new progress ID
        const taskData = {
            title: title,
            proj_id: parseInt(projectId),
            is_important: isImportant,
            is_urgent: isUrgent,
            energy_level: energy,
            state: state,
            progress_id: createdProgress.id
        };

        if (parentTaskId) {
            taskData.parent_task_id = parseInt(parentTaskId);
        }

        if (deadline) {
            taskData.deadline = new Date(deadline).toISOString();
        }

        console.log('Creating task with data:', taskData);

        const response = await fetch('/tasks/', {
            method: 'POST',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(taskData)
        });

        if (response.ok) {
            showToast('success', 'Success!', 'Task created successfully!');
            hideCreateTaskForm();
            await loadAllTasks();
            await loadProjects(); // Also reload projects to ensure project names are available
            // Refresh dashboard data without page reload
            await refreshDashboardData();
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to create task: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error creating task:', error);
        showToast('error', 'Error', `Error creating task: ${error.message}`);
    }
});

// Calendar functionality
let calendarActivities = [];

// Initialize calendar
function initializeCalendar() {
    renderCalendar();
    loadCalendarActivities();
}

// Render calendar for current month
function renderCalendar() {
    const year = currentCalendarDate.getFullYear();
    const month = currentCalendarDate.getMonth();
    
    // Update month/year display
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December'];
    document.getElementById('calendarMonthYear').textContent = `${monthNames[month]} ${year}`;
    
    // Get first day of month and number of days
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDay = firstDay.getDay();
    
    // Get today's date for highlighting
    const today = new Date();
    const isCurrentMonth = today.getFullYear() === year && today.getMonth() === month;
    
    let calendarHTML = '';
    
    // Add empty cells for days before the first day of the month
    for (let i = 0; i < startingDay; i++) {
        const prevMonthLastDay = new Date(year, month, 0).getDate();
        const dayNumber = prevMonthLastDay - startingDay + i + 1;
        calendarHTML += `<div class="calendar-day other-month">${dayNumber}</div>`;
    }
    
    // Add days of the current month
    for (let day = 1; day <= daysInMonth; day++) {
        // Instead of creating a Date object in the local timezone, construct the date string directly
        // and use the user's timezone for all comparisons and display
        const userTz = userTimezone || 'Asia/Tehran';
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;

        // Create a Date object at midnight in the user's timezone for display purposes only
        // (not for comparison)
        // For comparison, always use dateStr and the user's timezone

        // Get activities for this date in the user's timezone
        const activities = calendarActivities.filter(activity => {
            // Parse the activity clock_in as UTC, then convert to user's timezone and format as YYYY-MM-DD
            const utcDate = new Date(activity.clock_in);
            const activityDateStr = utcDate.toLocaleDateString('en-CA', { timeZone: userTz });
            return activityDateStr === dateStr;
        });

        // Debug: Log which activities are being mapped to this day in the calendar
        if (activities.length > 0) {
            console.log(`[CALENDAR DEBUG] Rendering box for ${dateStr} in timezone ${userTz}:`, activities.map(a => ({ id: a.id, clock_in: a.clock_in, task_id: a.task_id })));
        }
        
        let dayClasses = 'calendar-day';
        if (isCurrentMonth && today.getDate() === day) dayClasses += ' today';
        if (activities.length > 0) dayClasses += ' has-activities';
        
        let activitiesHTML = '';
        if (activities.length > 0) {
            activitiesHTML = '<div class="calendar-day-activities">';
            activities.slice(0, 3).forEach(activity => {
                const task = taskCache[activity.task_id];
                const taskTitle = task ? task.title : 'Unknown Task';
                activitiesHTML += `<div class="calendar-day-activity">${taskTitle}</div>`;
            });
            if (activities.length > 3) {
                activitiesHTML += `<div class="calendar-day-activity">+${activities.length - 3} more</div>`;
            }
            activitiesHTML += '</div>';
        }
        
        calendarHTML += `
            <div class="${dayClasses}" onclick="selectCalendarDate(${year}, ${month}, ${day})">
                <div class="calendar-day-number">${day}</div>
                ${activitiesHTML}
            </div>
        `;
    }
    
    // Add empty cells for days after the last day of the month
    const totalCells = startingDay + daysInMonth;
    const remainingCells = 42 - totalCells; // 6 rows * 7 days = 42
    for (let i = 0; i < remainingCells; i++) {
        const dayNumber = i + 1;
        calendarHTML += `<div class="calendar-day other-month">${dayNumber}</div>`;
    }
    
    document.getElementById('calendarDays').innerHTML = calendarHTML;
}

// Load activities for calendar
async function loadCalendarActivities() {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) return;

        // Use date-range endpoint with timezone parameter for better timezone handling
        const userTz = userTimezone || 'Asia/Tehran';
        const now = new Date();
        const todayInUserTz = new Date(now.toLocaleString('en-US', { timeZone: userTz }));
        const year = todayInUserTz.getFullYear();
        const month = String(todayInUserTz.getMonth() + 1).padStart(2, '0');
        const day = String(todayInUserTz.getDate()).padStart(2, '0');
        const todayStr = `${year}-${month}-${day}`;

        // Get activities for a wider range to ensure calendar coverage
        const startDate = new Date(todayInUserTz.getFullYear(), todayInUserTz.getMonth() - 1, 1);
        const endDate = new Date(todayInUserTz.getFullYear(), todayInUserTz.getMonth() + 2, 0);
        const startStr = startDate.toLocaleDateString('en-CA', { timeZone: userTz });
        const endStr = endDate.toLocaleDateString('en-CA', { timeZone: userTz });

        console.log('Loading calendar activities with timezone:', userTz);
        console.log('Today in user timezone:', todayStr);
        console.log('Date range:', startStr, 'to', endStr);

        const response = await fetch(`/activities/date-range?start_date=${startStr}&end_date=${endStr}&limit=1000&timezone=${encodeURIComponent(userTz)}`, {
            headers: {
                'X-API-Key': apiKey
            }
        });

        if (response.ok) {
            calendarActivities = await response.json();
            // Fetch and cache all unique task IDs for these activities
            const uniqueTaskIds = Array.from(new Set(calendarActivities.map(a => a.task_id).filter(Boolean)));
            await Promise.all(uniqueTaskIds.map(fetchAndCacheTask));
            console.log('Loaded calendar activities:', calendarActivities.length);
            console.log('Sample activities:', calendarActivities.slice(0, 3).map(a => ({
                id: a.id,
                clock_in: a.clock_in,
                task_id: a.task_id,
                status: a.status
            })));
            renderCalendar();
            loadUpcomingActivities();
            // Load today's reminders when calendar is initialized
            loadReminders();
        }
    } catch (error) {
        console.error('Error loading calendar activities:', error);
    }
}

// Check if a date has activities
function hasActivitiesOnDate(date) {
    const dateStr = formatDateForComparison(date, userTimezone);
    // Compare each activity's clock_in in the selected timezone
    const matchedActivities = calendarActivities.filter(activity => {
        const activityDate = new Date(activity.clock_in);
        const activityDateStr = formatDateForComparison(activityDate, userTimezone);
        return activityDateStr === dateStr;
    });
    // Debug output for July 8, 2025 in Paris
    if (
        userTimezone === 'Europe/Paris' &&
        dateStr === '2025-07-08'
    ) {
        console.log('DEBUG: Calendar dot activities for July 8, 2025 in Paris:', matchedActivities.map(a => ({ id: a.id, clock_in: a.clock_in, task_id: a.task_id })));
    }
    return matchedActivities.length > 0;
}

// Get activities for a specific date
function getActivitiesForDate(date) {
    const dateStr = formatDateForComparison(date, userTimezone);
    // Compare each activity's clock_in in the selected timezone
    const activities = calendarActivities.filter(activity => {
        const activityDate = new Date(activity.clock_in);
        const activityDateStr = formatDateForComparison(activityDate, userTimezone);
        return activityDateStr === dateStr;
    });
    // Debug output for July 8, 2025 in Paris
    if (
        userTimezone === 'Europe/Paris' &&
        dateStr === '2025-07-08'
    ) {
        console.log('DEBUG: Activities shown for July 8, 2025 in Paris:', activities.map(a => ({ id: a.id, clock_in: a.clock_in, task_id: a.task_id })));
    }
    return activities;
}

// Helper function to format date consistently for comparison
function formatDateForComparison(date, tz) {
    // Use Intl.DateTimeFormat to format the date in the selected timezone
    const formatter = new Intl.DateTimeFormat('en-CA', {
        timeZone: tz || userTimezone || 'Asia/Tehran',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    });
    // The format is always YYYY-MM-DD
    const parts = formatter.formatToParts(date);
    const year = parts.find(p => p.type === 'year').value;
    const month = parts.find(p => p.type === 'month').value;
    const day = parts.find(p => p.type === 'day').value;
    return `${year}-${month}-${day}`;
}

// Load upcoming activities for sidebar
function loadUpcomingActivities() {
    const userTz = userTimezone || 'Asia/Tehran';
    // Get current time in user's timezone for proper comparison
    const now = new Date();
    const nowInUserTz = new Date(now.toLocaleString('en-US', { timeZone: userTz }));
    console.log('Loading upcoming activities, current time in user timezone:', nowInUserTz);
    
    // Filter for PLANNED activities with clock_in time in the future
    const upcoming = calendarActivities
        .filter(activity => {
            const activityDate = new Date(activity.clock_in);
            const isPlanned = activity.status === 'PLANNED';
            const isInFuture = activityDate > nowInUserTz;
            
            console.log('Activity', activity.id, ':', {
                status: activity.status,
                clock_in: activity.clock_in,
                activityDate: activityDate,
                isPlanned: isPlanned,
                isInFuture: isInFuture,
                passes: isPlanned && isInFuture
            });
            
            return isPlanned && isInFuture;
        })
        .sort((a, b) => new Date(a.clock_in) - new Date(b.clock_in))
        .slice(0, 10);

    console.log('Found', upcoming.length, 'upcoming planned activities');

    let html = '';
    if (upcoming.length === 0) {
        html = '<p class="text-muted text-center">No upcoming planned activities</p>';
    } else {
        upcoming.forEach(activity => {
            const task = taskCache[activity.task_id];
            const project = projectsData.find(p => Number(p.id) === Number(task?.proj_id));
            const projectColor = project ? project.color || '#95a5a6' : '#95a5a6';
            const activityDate = new Date(activity.clock_in);
            const timeStr = activityDate.toLocaleTimeString('en-US', {
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                timeZone: userTimezone || 'Asia/Tehran'
            });
            const dateStr = activityDate.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                timeZone: userTimezone || 'Asia/Tehran'
            });

            // Calculate time until activity
            const timeUntil = activityDate - now;
            const hoursUntil = Math.floor(timeUntil / (1000 * 60 * 60));
            const minutesUntil = Math.floor((timeUntil % (1000 * 60 * 60)) / (1000 * 60));
            
            let timeUntilText = '';
            if (hoursUntil > 0) {
                timeUntilText = `in ${hoursUntil}h ${minutesUntil}m`;
            } else if (minutesUntil > 0) {
                timeUntilText = `in ${minutesUntil}m`;
            } else {
                timeUntilText = 'now';
            }

            html += `
                <div class="upcoming-activity-item ${activity.status.toLowerCase()}">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <div class="upcoming-activity-title">${task ? task.title : 'Unknown Task'}</div>
                            <div class="upcoming-activity-project" style="color: ${projectColor}">
                                ${project ? project.name : ''}
                            </div>
                        </div>
                        <div class="upcoming-activity-time text-end">
                            <span>${dateStr} ${timeStr}</span><br>
                            <small class="text-muted">${timeUntilText}</small>
                        </div>
                    </div>
                </div>
            `;
        });
    }

    document.getElementById('upcomingActivities').innerHTML = html;
}

// Calendar navigation functions
function previousMonth() {
    currentCalendarDate.setMonth(currentCalendarDate.getMonth() - 1);
    renderCalendar();
}

function nextMonth() {
    currentCalendarDate.setMonth(currentCalendarDate.getMonth() + 1);
    renderCalendar();
}

function goToToday() {
    const userTz = userTimezone || 'Asia/Tehran';
    // Set current date in user's timezone
    const now = new Date();
    currentCalendarDate = new Date(now.toLocaleString('en-US', { timeZone: userTz }));
    renderCalendar();
    
    // Get today's date string in user's timezone
    const todayStr = now.toLocaleDateString('en-CA', { timeZone: userTz });
    
    // Reset schedule title to default
    document.getElementById('scheduleTitle').textContent = "Today's Schedule";
    
    // Update date range filters to today
    document.getElementById('scheduleStartDate').value = todayStr;
    document.getElementById('scheduleEndDate').value = todayStr;
    
    // Clear activity filters and update filter object
    activityFilters = {
        status: '',
        task: '',
        startDate: todayStr,
        endDate: todayStr
    };
    
    // Clear the filter form elements
    const statusFilter = document.getElementById('activityStatusFilter');
    const taskFilter = document.getElementById('activityTaskFilter');
    if (statusFilter) statusFilter.value = '';
    if (taskFilter) taskFilter.value = '';
    
    // Reset pagination
    currentPage = 0;
    
    // Set filter type and load activities for today
    currentFilter = 'date-range';
    currentFilterParams = { start_date: todayStr, end_date: todayStr };
    
    // Clear scheduleData before loading new activities
    scheduleData = [];
    
    // Load activities for today
    loadActivitiesWithPagination();
    
    // Reset reminders to show today's reminders
    resetRemindersToToday();
    
    // Show success message
    showToast('success', 'Today', 'Showing today\'s activities and reminders');
}

// Select a date on the calendar
function selectCalendarDate(year, month, day) {
    console.log('selectCalendarDate called with:', year, month, day);
    
    // Create the date in the user's timezone to avoid timezone conversion issues
    const userTz = userTimezone || 'Asia/Tehran';
    
    // Create a date string directly in the user's timezone
    // This avoids timezone conversion issues by creating the date string in the user's timezone
    const formattedDate = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    console.log('Formatted date in user timezone:', formattedDate);
    
    // Create a Date object for display purposes in the user's timezone
    // Use the user's timezone to create the date string for display
    const selectedDate = new Date(`${formattedDate}T00:00:00`);
    
    // Update the date range filters
    document.getElementById('scheduleStartDate').value = formattedDate;
    document.getElementById('scheduleEndDate').value = formattedDate;
    
    // Clear activity filters and update filter object
    activityFilters = {
        status: '',
        task: '',
        startDate: formattedDate,
        endDate: formattedDate
    };
    console.log('Updated activityFilters:', activityFilters);
    
    // Clear the filter form elements
    const statusFilter = document.getElementById('activityStatusFilter');
    const taskFilter = document.getElementById('activityTaskFilter');
    if (statusFilter) statusFilter.value = '';
    if (taskFilter) taskFilter.value = '';
    
    // Reset pagination
    currentPage = 0;
    
    // Set filter type and load activities
    currentFilter = 'date-range';
    currentFilterParams = { start_date: formattedDate, end_date: formattedDate };
    console.log('Set currentFilter:', currentFilter);
    console.log('Set currentFilterParams:', currentFilterParams);
    
    // Clear scheduleData before loading new activities
    scheduleData = [];
    console.log('Cleared scheduleData');
    
    // Load activities for the selected date
    console.log('About to load activities for date:', formattedDate);
    console.log('Current scheduleData before loading:', scheduleData);
    loadActivitiesWithPagination();
    
    // Load reminders for the selected date
    loadRemindersForDate(formattedDate);
    
    // Update reminders section title to show the selected date
    updateRemindersSectionTitle(formattedDate);
    
    // Create the display date string directly in the user's timezone
    // This avoids timezone conversion issues by formatting the date string directly
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December'];
    const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    
    // Calculate the day of week for the selected date
    const tempDate = new Date(year, month, day);
    const dayOfWeek = dayNames[tempDate.getDay()];
    const monthName = monthNames[month];
    const dateStr = `${dayOfWeek}, ${monthName} ${day}, ${year}`;

    // Check if the selected date is today in the user's timezone
    const now = new Date();
    const todayStr = now.toLocaleDateString('en-CA', { timeZone: userTz });
    const selectedStr = tempDate.toLocaleDateString('en-CA', { timeZone: userTz });
    if (selectedStr === todayStr) {
        document.getElementById('scheduleTitle').textContent = "Today's Schedule";
    } else {
        document.getElementById('scheduleTitle').textContent = `Activities for ${dateStr}`;
    }
    
    // Scroll to the schedule section
    document.querySelector('.card-header h5').scrollIntoView({ behavior: 'smooth' });
    
    // Show success message
    showToast('info', 'Date Selected', `Showing activities for ${dateStr}`);
}

// Initialize calendar when dashboard loads
document.addEventListener('DOMContentLoaded', function() {
    // Add calendar initialization to the existing initialization
    setTimeout(() => {
        initializeCalendar();
    }, 1000); // Small delay to ensure other data is loaded
});

// Reminders functionality
let remindersData = [];
let reminderDateRange = { start: null, end: null };

// Load reminders for a date range or today if no range
async function loadReminders() {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) return;

        let url = '/reminders/today';
        const userTz = userTimezone || 'Asia/Tehran';
        if (reminderDateRange.start && reminderDateRange.end) {
            url = `/reminders/date-range?start_date=${reminderDateRange.start}&end_date=${reminderDateRange.end}&timezone=${encodeURIComponent(userTz)}`;
        }

        const response = await fetch(url, {
            headers: {
                'X-API-Key': apiKey
            }
        });

        if (response.ok) {
            remindersData = await response.json();
            displayReminders();
        } else {
            console.error('Failed to load reminders:', response.status);
        }
    } catch (error) {
        console.error('Error loading reminders:', error);
    }
    updateRemindersSectionTitle();
}

function applyReminderDateRange() {
    const start = document.getElementById('reminderStartDate').value;
    const end = document.getElementById('reminderEndDate').value;
    if (!start || !end) {
        showToast('warning', 'Validation Error', 'Please select both start and end dates');
        return;
    }
    reminderDateRange.start = start;
    reminderDateRange.end = end;
    loadReminders();
    updateRemindersSectionTitle();
}

function clearReminderDateRange() {
    document.getElementById('reminderStartDate').value = '';
    document.getElementById('reminderEndDate').value = '';
    reminderDateRange.start = null;
    reminderDateRange.end = null;
    loadReminders();
    updateRemindersSectionTitle();
}

// Load reminders for a specific date
async function loadRemindersForDate(dateStr) {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) return;

        const userTz = userTimezone || 'Asia/Tehran';
        const url = `/reminders/date-range?start_date=${dateStr}&end_date=${dateStr}&timezone=${encodeURIComponent(userTz)}`;

        console.log('Loading reminders for date:', dateStr, 'with URL:', url);

        const response = await fetch(url, {
            headers: {
                'X-API-Key': apiKey
            }
        });

        if (response.ok) {
            remindersData = await response.json();
            console.log('Loaded reminders for date:', dateStr, 'count:', remindersData.length);
            displayReminders();
            updateRemindersSectionTitle(dateStr);
        } else {
            console.error('Failed to load reminders for date:', response.status);
        }
    } catch (error) {
        console.error('Error loading reminders for date:', error);
    }
}

// Reset reminders to show today's reminders
function resetRemindersToToday() {
    // Clear any date range filters
    document.getElementById('reminderStartDate').value = '';
    document.getElementById('reminderEndDate').value = '';
    reminderDateRange.start = null;
    reminderDateRange.end = null;
    
    // Load today's reminders
    loadReminders();
    
    // Update the section title back to "Today's Reminders"
    document.getElementById('remindersSectionTitle').innerHTML = '<i class="bi bi-bell me-2"></i>Today\'s Reminders';
    
    // Also reset activities to show today's activities
    const userTz = userTimezone || 'Asia/Tehran';
    const now = new Date();
    const todayStr = now.toLocaleDateString('en-CA', { timeZone: userTz });
    
    // Update date range filters to today
    document.getElementById('scheduleStartDate').value = todayStr;
    document.getElementById('scheduleEndDate').value = todayStr;
    
    // Clear activity filters and update filter object
    activityFilters = {
        status: '',
        task: '',
        startDate: todayStr,
        endDate: todayStr
    };
    
    // Clear the filter form elements
    const statusFilter = document.getElementById('activityStatusFilter');
    const taskFilter = document.getElementById('activityTaskFilter');
    if (statusFilter) statusFilter.value = '';
    if (taskFilter) taskFilter.value = '';
    
    // Reset pagination
    currentPage = 0;
    
    // Set filter type and load activities for today
    currentFilter = 'date-range';
    currentFilterParams = { start_date: todayStr, end_date: todayStr };
    
    // Clear scheduleData before loading new activities
    scheduleData = [];
    
    // Load activities for today
    loadActivitiesWithPagination();
    
    // Reset schedule title to today
    document.getElementById('scheduleTitle').textContent = "Today's Schedule";
    
    // Show success message
    showToast('success', 'Reset', 'Showing today\'s activities and reminders');
}

// Display reminders in the UI
async function displayReminders() {
    await ensureTasksForReminders(remindersData);
    const remindersList = document.getElementById('remindersList');
    if (remindersData.length === 0) {
        // Check if we're showing reminders for a specific date or today
        const titleEl = document.getElementById('remindersSectionTitle');
        const titleText = titleEl.textContent || titleEl.innerText;
        
        if (titleText.includes("Today's Reminders")) {
            remindersList.innerHTML = '<p class="text-muted text-center">No reminders for today</p>';
        } else {
            remindersList.innerHTML = '<p class="text-muted text-center">No reminders for this date</p>';
        }
        return;
    }
    let html = '';
    remindersData.forEach(reminder => {
        let when;
        if (typeof reminder.when === 'string') {
            when = new Date(reminder.when);
        } else {
            when = new Date(reminder.when);
        }
        const dateTimeStr = when.toLocaleString('en-US', {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
            hour12: false,
            timeZone: userTimezone || 'Asia/Tehran'
        });
        const now = new Date();
        const isOverdue = when < now;
        const overdueClass = isOverdue ? 'text-danger' : 'text-muted';
        // Use taskCache for task name
        let taskTitle = '';
        if (reminder.task_id && taskCache[reminder.task_id]) {
            taskTitle = `<div class='small text-muted'>Task: ${taskCache[reminder.task_id].title}</div>`;
        }
        // Determine direction for description
        let descDir = 'ltr';
        let descAlign = 'left';
        const desc = reminder.note || '';
        if (desc.length > 0) {
            const firstChar = desc.trim().charAt(0);
            if (/^[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/.test(firstChar)) {
                descDir = 'rtl';
                descAlign = 'right';
            } else if (/^[A-Za-z]/.test(firstChar)) {
                descDir = 'ltr';
                descAlign = 'left';
            }
        }
        html += `
            <div class="reminder-item border rounded p-1 mb-1 ${isOverdue ? 'border-danger' : 'border-light'}" style="font-size:0.92em; cursor:pointer; position:relative;" onclick="if(event.target.classList.contains('reminder-delete-tick')) return; editReminder(${reminder.id})">
                <div class="d-flex justify-content-between align-items-center">
                    <div class="flex-grow-1">
                        <div class="d-flex align-items-center mb-1" style="gap:4px;">
                            <i class="bi bi-bell ${overdueClass}" style="font-size:1em;"></i>
                            <span class="fw-bold ${overdueClass}" style="font-size:0.98em;">${dateTimeStr}</span>
                            ${isOverdue ? '<span class=\"badge bg-danger ms-1\" style=\"font-size:0.8em;\">Overdue</span>' : ''}
                        </div>
                        <p class="mb-0" style="line-height:1.3;"><span dir="${descDir}" style="text-align:${descAlign};display:block;">${desc}</span></p>
                        ${taskTitle}
                    </div>
                    <div class="d-flex align-items-center">
                        <span class="reminder-delete-tick" title="Delete Reminder" style="cursor:pointer; color:#dc3545; font-size:1.3em; padding:0 0.4em; user-select:none;" onclick="event.stopPropagation(); deleteReminder(${reminder.id})">✔</span>
                    </div>
                </div>
            </div>
        `;
    });
    remindersList.innerHTML = html;
}

// Helper to convert local datetime-local value to UTC ISO string
function localDateTimeToUTCISOString(localDateTimeStr) {
    // localDateTimeStr is like '2024-07-10T14:00'
    // Simply append seconds and timezone info to make it a valid ISO string
    // This avoids double timezone conversion issues
    return localDateTimeStr + ':00.000Z';
}

// Create reminder function
async function createReminder(event) {
    if (event) event.preventDefault();
    console.log('Create reminder button clicked!');
    
    const when = document.getElementById('reminderWhen').value;
    const note = document.getElementById('reminderNote').value;

    console.log('Form values:', { when, note });

    if (!when || !note) {
        showToast('warning', 'Validation Error', 'Please fill in all required fields');
        return;
    }

    try {
        const apiKey = localStorage.getItem('apiKey');
        console.log('API Key found:', !!apiKey);
        
        // Convert local datetime to UTC ISO string for backend
        const localDateTime = new Date(when);
        const utcDateTime = localDateTime.toISOString();
        console.log('Local datetime:', when);
        console.log('UTC datetime:', utcDateTime);
        
        const requestBody = {
            when: utcDateTime, // Send UTC time to backend
            note: note
        };
        console.log('Request body:', requestBody);
        
        const response = await fetch('/reminders/', {
            method: 'POST',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        console.log('Response status:', response.status);
        console.log('Response ok:', response.ok);

        if (response.ok) {
            const result = await response.json();
            console.log('Reminder created successfully:', result);
            showToast('success', 'Success!', 'Reminder created successfully!');
            
            // Close modal and reset form
            const modal = bootstrap.Modal.getInstance(document.getElementById('newReminderModal'));
            modal.hide();
            document.getElementById('newReminderForm').reset();
            
            // Reload reminders
            await loadReminders();
            
            // Refresh dashboard data without page reload
            await refreshDashboardData();
        } else {
            const errorData = await response.json();
            console.error('Server error:', errorData);
            showToast('error', 'Error', `Failed to create reminder: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error creating reminder:', error);
        showToast('error', 'Error', `Error creating reminder: ${error.message}`);
    }
}

// Edit reminder
async function editReminder(reminderId) {
    try {
        const apiKey = localStorage.getItem('apiKey');
        const response = await fetch(`/reminders/${reminderId}`, {
            headers: {
                'X-API-Key': apiKey
            }
        });

        if (response.ok) {
            const reminder = await response.json();
            
            // Convert UTC time from backend to user's timezone for display
            const utcDate = new Date(reminder.when);
            const userTz = userTimezone || 'Asia/Tehran';
            const localDate = new Date(utcDate.toLocaleString('en-US', { timeZone: userTz }));
            
            // Populate the edit form
            document.getElementById('editReminderId').value = reminder.id;
            document.getElementById('editReminderWhen').value = formatDateTimeForInput(localDate);
            document.getElementById('editReminderNote').value = reminder.note;
            
            // Show the modal
            const modal = new bootstrap.Modal(document.getElementById('editReminderModal'));
            modal.show();
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to load reminder: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error loading reminder for edit:', error);
        showToast('error', 'Error', `Error loading reminder: ${error.message}`);
    }
}

// Update reminder function
async function updateReminder(event) {
    if (event) event.preventDefault();
    const reminderId = document.getElementById('editReminderId').value;
    const when = document.getElementById('editReminderWhen').value;
    const note = document.getElementById('editReminderNote').value;

    if (!when || !note) {
        showToast('warning', 'Validation Error', 'Please fill in all required fields');
        return;
    }

    try {
        const apiKey = localStorage.getItem('apiKey');
        // Convert local datetime to UTC ISO string for backend
        const localDateTime = new Date(when);
        const utcDateTime = localDateTime.toISOString();
        const response = await fetch(`/reminders/${reminderId}`, {
            method: 'PUT',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                when: utcDateTime, // Send UTC time to backend
                note: note
            })
        });
        if (response.ok) {
            showToast('success', 'Success!', 'Reminder updated successfully!');
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('editReminderModal'));
            modal.hide();
            // Reload reminders
            await loadReminders();
            // No page reload!
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to update reminder: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error updating reminder:', error);
        showToast('error', 'Error', `Error updating reminder: ${error.message}`);
    }
}

// Delete reminder
async function deleteReminder(reminderId) {
    // Show confirmation modal
    const confirmModal = new bootstrap.Modal(document.getElementById('confirmDeleteModal'));
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    const cancelBtn = document.getElementById('cancelDeleteBtn');
    const modalBody = document.getElementById('confirmDeleteBody');
    
    modalBody.textContent = 'Are you sure you want to delete this reminder? This action cannot be undone.';
    
    // Set up confirmation handler
    const handleConfirm = async () => {
        confirmModal.hide();
        await performReminderDeletion(reminderId);
        // Clean up event listeners
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', handleCancel);
    };
    
    const handleCancel = () => {
        confirmModal.hide();
        // Clean up event listeners
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', handleCancel);
    };
    
    confirmBtn.addEventListener('click', handleConfirm);
    cancelBtn.addEventListener('click', handleCancel);
    
    confirmModal.show();
}

// Perform the actual reminder deletion
async function performReminderDeletion(reminderId) {
    try {
        const apiKey = localStorage.getItem('apiKey');
        const response = await fetch(`/reminders/${reminderId}`, {
            method: 'DELETE',
            headers: {
                'X-API-Key': apiKey
            }
        });

        if (response.ok) {
            showToast('success', 'Success!', 'Reminder deleted successfully!');
            await loadReminders();
            // No page reload!
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to delete reminder: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error deleting reminder:', error);
        showToast('error', 'Error', `Error deleting reminder: ${error.message}`);
    }
}

// Set default reminder time to now in user's timezone
function setDefaultReminderTime() {
    const now = new Date();
    const userTz = userTimezone || 'Asia/Tehran';
    
    // Convert current time to user's timezone
    const localTime = new Date(now.toLocaleString('en-US', { timeZone: userTz }));
    const defaultTime = formatDateTimeForInput(localTime);
    document.getElementById('reminderWhen').value = defaultTime;
}

// Initialize reminder functionality
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing reminder functionality...');
    setTimeout(() => {
        loadReminders();
        setDefaultReminderTime();
    }, 1500);
});

// Add event listener for reminder modal
document.addEventListener('DOMContentLoaded', function() {
    const reminderModal = document.getElementById('newReminderModal');
    if (reminderModal) {
        reminderModal.addEventListener('show.bs.modal', function() {
            console.log('Reminder modal opened');
            setDefaultReminderTime();
        });
    } else {
        console.error('Reminder modal not found!');
    }
});

// Timezone management
// Load user timezone
async function loadUserTimezone() {
    console.log('loadUserTimezone called - version 1.3');
    try {
        const apiKey = localStorage.getItem('apiKey');
        const response = await fetch('/users/timezone', {
            headers: {
                'X-API-Key': apiKey
            }
        });

        if (response.ok) {
            const data = await response.json();
            console.log('Timezone response data:', data);
            userTimezone = data.timezone;
            availableTimezones = data.available_timezones;
            console.log('Available timezones:', availableTimezones);
            console.log('Available timezones type:', typeof availableTimezones);
            console.log('Available timezones keys:', Object.keys(availableTimezones));
            updateTimezoneInfo();
        }
    } catch (error) {
        console.error('Error loading user timezone:', error);
    }
}

// Update timezone info display
function updateTimezoneInfo() {
    const timezoneInfo = document.getElementById('timezoneInfo');
    if (timezoneInfo) {
        const now = new Date();
        const timeString = now.toLocaleTimeString('en-US', {
            hour12: false,
            timeZone: userTimezone
        });
        const timezoneAbbr = getTimezoneAbbreviation(userTimezone);
        timezoneInfo.textContent = `${timeString} ${timezoneAbbr}`;
    }
}

// Get timezone abbreviation
function getTimezoneAbbreviation(timezone) {
    const date = new Date();
    const options = { 
        timeZoneName: 'short',
        timeZone: timezone || userTimezone || 'Asia/Tehran'
    };
    return date.toLocaleDateString('en-US', options).split(', ')[1];
}

// Open timezone settings modal
async function openTimezoneSettings() {
    console.log('openTimezoneSettings called - version 1.3');
    // Ensure timezone data is loaded before opening modal
    if (!availableTimezones || Object.keys(availableTimezones).length === 0) {
        console.log('Timezone data not loaded, loading now...');
        await loadUserTimezone();
    }
    
    const modal = new bootstrap.Modal(document.getElementById('timezoneSettingsModal'));
    populateTimezoneCountrySelect();
    setupTimezoneEventListeners(); // Set up event listeners after modal is opened
    modal.show();
}

// Populate country dropdown
function populateTimezoneCountrySelect() {
    console.log('populateTimezoneCountrySelect called');
    console.log('availableTimezones:', availableTimezones);
    console.log('availableTimezones type:', typeof availableTimezones);
    
    const countrySelect = document.getElementById('timezoneCountrySelect');
    const citySelect = document.getElementById('timezoneCitySelect');
    countrySelect.innerHTML = '';
    citySelect.innerHTML = '<option value="">Select a country first</option>';
    citySelect.disabled = true;
    
    const countries = Object.keys(availableTimezones);
    console.log('Countries found:', countries);
    countrySelect.innerHTML = '<option value="">Choose a country...</option>';
    countries.forEach(country => {
        console.log('Processing country:', country);
        console.log('Country data:', availableTimezones[country]);
        
        // Check if this is a valid country (not a numeric key)
        if (isNaN(country)) {
            const option = document.createElement('option');
            option.value = country;
            option.textContent = country;
            countrySelect.appendChild(option);
        } else {
            console.warn('Skipping numeric key:', country);
        }
    });
    
    // Try to preselect the country/city based on current timezone
    let found = false;
    countries.forEach(country => {
        if (!Array.isArray(availableTimezones[country])) {
            console.error('Timezone data for country is not an array:', country, availableTimezones[country]);
            return;
        }
        availableTimezones[country].forEach(cityObj => {
            if (cityObj.value === userTimezone) {
                countrySelect.value = country;
                populateTimezoneCitySelect();
                citySelect.value = cityObj.value;
                selectedCountry = country;
                selectedCity = cityObj.city;
                selectedTimezoneValue = cityObj.value;
                found = true;
            }
        });
    });
    if (!found) {
        selectedCountry = '';
        selectedCity = '';
        selectedTimezoneValue = '';
    }
}

// Populate city dropdown when country changes
function populateTimezoneCitySelect() {
    console.log('populateTimezoneCitySelect called');
    const countrySelect = document.getElementById('timezoneCountrySelect');
    const citySelect = document.getElementById('timezoneCitySelect');
    const country = countrySelect.value;
    console.log('Selected country:', country);
    
    citySelect.innerHTML = '';
    if (!country || !availableTimezones[country] || !Array.isArray(availableTimezones[country])) {
        console.log('No valid country selected or no data for country:', country);
        citySelect.innerHTML = '<option value="">Select a country first</option>';
        citySelect.disabled = true;
        if (country && !Array.isArray(availableTimezones[country])) {
            console.error('Timezone data for country is not an array:', country, availableTimezones[country]);
        }
        return;
    }
    
    console.log('Populating cities for country:', country);
    console.log('Cities data:', availableTimezones[country]);
    
    citySelect.disabled = false;
    citySelect.innerHTML = '<option value="">Choose a city...</option>';
    availableTimezones[country].forEach(cityObj => {
        console.log('Adding city option:', cityObj);
        const option = document.createElement('option');
        option.value = cityObj.value;
        option.textContent = cityObj.label;
        citySelect.appendChild(option);
    });
    
    // If user's timezone matches, preselect
    availableTimezones[country].forEach(cityObj => {
        if (cityObj.value === userTimezone) {
            citySelect.value = cityObj.value;
            selectedCity = cityObj.city;
            selectedTimezoneValue = cityObj.value;
        }
    });
    
    console.log('City dropdown populated with', availableTimezones[country].length, 'cities');
}

// Set up timezone modal event listeners
function setupTimezoneEventListeners() {
    const countrySelect = document.getElementById('timezoneCountrySelect');
    const citySelect = document.getElementById('timezoneCitySelect');
    
    if (countrySelect) {
        countrySelect.addEventListener('change', function() {
            console.log('Country changed to:', countrySelect.value);
            populateTimezoneCitySelect();
            updateTimezonePreview();
        });
    }
    
    if (citySelect) {
        citySelect.addEventListener('change', function() {
            console.log('City changed to:', citySelect.value);
            selectedTimezoneValue = citySelect.value;
            updateTimezonePreview();
        });
    }
}

// Update timezone preview
function updateTimezonePreview() {
    const citySelect = document.getElementById('timezoneCitySelect');
    const preview = document.getElementById('timezonePreview');
    const selectedTimezone = citySelect.value;
    
    if (selectedTimezone) {
        const now = new Date();
        const timeString = now.toLocaleTimeString('en-US', {
            hour12: false,
            timeZone: selectedTimezone
        });
        const timezoneAbbr = getTimezoneAbbreviation(selectedTimezone);
        preview.textContent = `${timeString} ${timezoneAbbr}`;
    } else {
        preview.textContent = '--:--';
    }
}

// Update user timezone
async function updateTimezone() {
    const citySelect = document.getElementById('timezoneCitySelect');
    const newTimezone = citySelect.value;
    
    if (!newTimezone) {
        showToast('warning', 'Validation Error', 'Please select a city');
        return;
    }

    try {
        const apiKey = localStorage.getItem('apiKey');
        const response = await fetch('/users/timezone', {
            method: 'POST',
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                timezone: newTimezone
            })
        });

        if (response.ok) {
            userTimezone = newTimezone;
            updateTimezoneInfo();
            setCurrentTime();
            setTodayDate();
            showToast('success', 'Success!', 'Timezone updated successfully!');
            const modal = bootstrap.Modal.getInstance(document.getElementById('timezoneSettingsModal'));
            modal.hide();
            await refreshDashboardData();
            await loadCalendarActivities();
            renderCalendar();
            loadUpcomingActivities();
            await loadReminders();
            updateTimezoneInfo();
            // Update current activity display with new timezone
            await checkForPlannedActivities();
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to update timezone: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error updating timezone:', error);
        showToast('error', 'Error', `Error updating timezone: ${error.message}`);
    }
}

// Add event listener for timezone select change
document.addEventListener('DOMContentLoaded', function() {
    const timezoneSelect = document.getElementById('timezoneSelect');
    if (timezoneSelect) {
        timezoneSelect.addEventListener('change', updateTimezonePreview);
    }
});

// Timezone functionality is now loaded in the main initialization sequence

window.applyReminderDateRange = applyReminderDateRange;
window.clearReminderDateRange = clearReminderDateRange;
window.resetRemindersToToday = resetRemindersToToday;
window.previousMonth = previousMonth;
window.nextMonth = nextMonth;
window.goToToday = goToToday;

function updateRemindersSectionTitle(dateStr = null) {
    const titleEl = document.getElementById('remindersSectionTitle');
    console.log('Updating reminders section title with dateStr:', dateStr);
    
    if (dateStr) {
        // Format the date for display
        const date = new Date(dateStr);
        const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                           'July', 'August', 'September', 'October', 'November', 'December'];
        const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        const dayOfWeek = dayNames[date.getDay()];
        const monthName = monthNames[date.getMonth()];
        const day = date.getDate();
        const year = date.getFullYear();
        
        // Check if it's today
        const now = new Date();
        const todayStr = now.toLocaleDateString('en-CA', { timeZone: userTimezone || 'Asia/Tehran' });
        const selectedStr = date.toLocaleDateString('en-CA', { timeZone: userTimezone || 'Asia/Tehran' });
        
        console.log('Date comparison - todayStr:', todayStr, 'selectedStr:', selectedStr);
        
        if (selectedStr === todayStr) {
            titleEl.innerHTML = '<i class="bi bi-bell me-2"></i>Today\'s Reminders';
        } else {
            titleEl.innerHTML = `<i class="bi bi-bell me-2"></i>Reminders for ${dayOfWeek}, ${monthName} ${day}, ${year}`;
        }
        
        console.log('Updated title to:', titleEl.innerHTML);
    } else if (reminderDateRange.start && reminderDateRange.end) {
        if (reminderDateRange.start === reminderDateRange.end) {
            titleEl.innerHTML = `<i class="bi bi-bell me-2"></i>Reminders for ${reminderDateRange.start}`;
        } else {
            titleEl.innerHTML = `<i class="bi bi-bell me-2"></i>Reminders (${reminderDateRange.start} to ${reminderDateRange.end})`;
        }
    } else {
        titleEl.innerHTML = '<i class="bi bi-bell me-2"></i>Today\'s Reminders';
    }
}

function displaySchedule() {
    const scheduleList = document.getElementById('scheduleList');
    if (!scheduleList) return;
    if (!scheduleData || scheduleData.length === 0) {
        scheduleList.innerHTML = '<p class="text-muted text-center">No activities scheduled for today.</p>';
        return;
    }
    let html = '';
    function getContrastYIQ(hexcolor) {
        hexcolor = hexcolor.replace('#', '');
        if (hexcolor.length === 3) hexcolor = hexcolor[0]+hexcolor[0]+hexcolor[1]+hexcolor[1]+hexcolor[2]+hexcolor[2];
        const r = parseInt(hexcolor.substr(0,2),16);
        const g = parseInt(hexcolor.substr(2,2),16);
        const b = parseInt(hexcolor.substr(4,2),16);
        const yiq = ((r*299)+(g*587)+(b*114))/1000;
        return (yiq >= 128) ? 'black' : 'white';
    }
    scheduleData.forEach(activity => {
        const task = taskCache[activity.task_id];
        const taskTitle = task ? task.title : 'Unknown Task';
        const project = task && projectCache[task.proj_id] ? projectCache[task.proj_id] : null;
        const projectName = project ? project.name : '';
        const projectColor = project ? project.color : '#95a5a6';
        const projectTextColor = getContrastYIQ(projectColor);
        const clockIn = new Date(activity.clock_in);
        const clockOut = activity.clock_out ? new Date(activity.clock_out) : null;
        const timeStr = clockIn.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', timeZone: userTimezone || 'Asia/Tehran' });
        const endTimeStr = clockOut ? clockOut.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', timeZone: userTimezone || 'Asia/Tehran' }) : '';
        const description = activity.description ? activity.description.replace(/"/g, '&quot;') : '';
        html += `
            <div class="schedule-item border rounded p-2 mb-2 d-flex align-items-center" style="min-height: 38px; max-height: 38px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;" title="${description}">
                <span class="fw-bold text-truncate me-2" style="max-width: 22%">${taskTitle}</span>
                <span class='badge rounded-pill text-truncate me-2' style='background:${projectColor};color:${projectTextColor};max-width: 16%'>${projectName}</span>
                <span class="badge bg-${activity.status === 'PLANNED' ? 'info' : activity.status === 'DOING' ? 'success' : 'secondary'} me-2">${activity.status}</span>
                <span class="small text-muted me-2" style="white-space:nowrap;"><i class="bi bi-clock me-1"></i>${timeStr}${endTimeStr ? ' - ' + endTimeStr : ''}</span>
                <div class="d-flex gap-1 ms-auto flex-shrink-0">
                    <button class="btn btn-sm btn-outline-primary" title="Edit Activity" onclick="editActivity(${activity.id})"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-sm btn-outline-danger" title="Delete Activity" onclick="deleteActivity(${activity.id})"><i class="bi bi-trash"></i></button>
                </div>
            </div>
        `;
    });
    scheduleList.innerHTML = html;
}

function populateEditActivityProjectSelect() {
    const select = document.getElementById('editActivityProject');
    if (!select) return;
    select.innerHTML = '<option value="">Choose a project...</option>';
    projectsData.forEach(project => {
        const option = document.createElement('option');
        option.value = project.id;
        option.textContent = project.name;
        select.appendChild(option);
    });
}

function populateEditActivityTasks() {
    const projectSelect = document.getElementById('editActivityProject');
    const taskSelect = document.getElementById('editActivityTask');
    if (!projectSelect || !taskSelect) return;
    const selectedProjectId = projectSelect.value;
    // Reset task select
    taskSelect.innerHTML = '<option value="">Choose a task...</option>';
    taskSelect.disabled = true;
    if (!selectedProjectId) {
        return;
    }
    // Enable task select
    taskSelect.disabled = false;
    // Filter tasks by selected project
    const projectTasks = tasksData.filter(task => 
        String(task.proj_id) === String(selectedProjectId) && 
        task.state !== 'done' && 
        task.state !== 'closed'
    );
    projectTasks.forEach(task => {
        const option = document.createElement('option');
        option.value = task.id;
        option.textContent = task.title;
        taskSelect.appendChild(option);
    });
}

function updatePaginationInfo() {
    // Calculate the current range of activities being shown
    const start = totalActivities === 0 ? 0 : (currentPage * pageSize) + 1;
    const end = Math.min((currentPage + 1) * pageSize, totalActivities);
    // Update the DOM elements
    const currentRange = document.getElementById('currentRange');
    const totalCount = document.getElementById('totalCount');
    if (currentRange && totalCount) {
        currentRange.textContent = `${start}-${end}`;
        totalCount.textContent = totalActivities;
    }
}

// Helper function for text color contrast
function getContrastYIQ(hexcolor) {
    hexcolor = hexcolor.replace('#', '');
    if (hexcolor.length === 3) hexcolor = hexcolor[0]+hexcolor[0]+hexcolor[1]+hexcolor[1]+hexcolor[2]+hexcolor[2];
    const r = parseInt(hexcolor.substr(0,2),16);
    const g = parseInt(hexcolor.substr(2,2),16);
    const b = parseInt(hexcolor.substr(4,2),16);
    const yiq = ((r*299)+(g*587)+(b*114))/1000;
    return (yiq >= 128) ? 'black' : 'white';
}

// Add this function near other populate functions:
function populateActivityProjectSelect() {
    const select = document.getElementById('activityProject');
    if (!select) return;
    select.innerHTML = '<option value="">Choose a project...</option>';
    projectsData.forEach(project => {
        const option = document.createElement('option');
        option.value = project.id;
        option.textContent = project.name;
        select.appendChild(option);
    });
}

function populateActivityTasks() {
    const projectSelect = document.getElementById('activityProject');
    const taskSelect = document.getElementById('activityTask');
    if (!projectSelect || !taskSelect) return;
    const selectedProjectId = projectSelect.value;
    // Reset task select
    taskSelect.innerHTML = '<option value="">Choose a task...</option>';
    taskSelect.disabled = true;
    if (!selectedProjectId) {
        return;
    }
    // Enable task select
    taskSelect.disabled = false;
    // Filter tasks by selected project, excluding done and closed
    const projectTasks = tasksData.filter(task => 
        String(task.proj_id) === String(selectedProjectId) && 
        task.state !== 'done' && 
        task.state !== 'closed'
    );
    projectTasks.forEach(task => {
        const option = document.createElement('option');
        option.value = task.id;
        option.textContent = task.title;
        taskSelect.appendChild(option);
    });
}

// Helper to set currentActivity to the most recent 'DOING' activity and update the display
function setCurrentDoingActivityFromSchedule() {
    if (scheduleData && scheduleData.length > 0) {
        // Find all DOING activities
        const doingActivities = scheduleData.filter(a => a.status === 'DOING');
        if (doingActivities.length > 0) {
            // Pick the most recent one (latest clock_in)
            doingActivities.sort((a, b) => new Date(b.clock_in) - new Date(a.clock_in));
            currentActivity = doingActivities[0];
            updateCurrentActivityDisplay(true);
            return;
        }
    }
    // If none found, clear currentActivity section
    currentActivity = null;
    document.getElementById('currentActivityInfo').innerHTML = `<p class="mb-1">No active activity</p><small>Click \"Clock In\" to start tracking your work</small>`;
    document.getElementById('startTime').textContent = '--:--';
}

// Delete Task Function
async function deleteTask(taskId) {
    // Show confirmation modal
    const confirmModal = new bootstrap.Modal(document.getElementById('confirmDeleteModal'));
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    const cancelBtn = document.getElementById('cancelDeleteBtn');
    const modalBody = document.getElementById('confirmDeleteBody');
    
    modalBody.textContent = 'Are you sure you want to delete this task? This action cannot be undone and will also delete all associated activities and progress data.';
    
    // Set up confirmation handler
    const handleConfirm = async () => {
        confirmModal.hide();
        await performTaskDeletion(taskId);
        // Clean up event listeners
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', handleCancel);
    };
    
    const handleCancel = () => {
        confirmModal.hide();
        // Clean up event listeners
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', handleCancel);
    };
    
    confirmBtn.addEventListener('click', handleConfirm);
    cancelBtn.addEventListener('click', handleCancel);
    
    confirmModal.show();
}

// Perform the actual task deletion
async function performTaskDeletion(taskId) {
    try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
            showToast('error', 'Error', 'No API key found. Please log in again.');
            window.location.href = '/login';
            return;
        }

        const response = await fetch(`/tasks/${taskId}`, {
            method: 'DELETE',
            headers: {
                'X-API-Key': apiKey
            }
        });

        if (response.ok) {
            // Close the edit task modal
            const editTaskModal = bootstrap.Modal.getInstance(document.getElementById('editTaskModal'));
            editTaskModal.hide();
            
            showToast('success', 'Success!', 'Task deleted successfully!');
            await loadAllTasks();
            // Refresh dashboard data without page reload
            await refreshDashboardData();
        } else {
            const errorData = await response.json();
            showToast('error', 'Error', `Failed to delete task: ${errorData.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error deleting task:', error);
        showToast('error', 'Error', `Error deleting task: ${error.message}`);
    }
}

// Add event listener for delete task button
document.getElementById('deleteTaskBtn').addEventListener('click', function() {
    console.log('Delete task button clicked!');
    const taskId = document.getElementById('editTaskId').value;
    console.log('Task ID to delete:', taskId);
    if (taskId) {
        console.log('Calling deleteTask function...');
        deleteTask(taskId);
    } else {
        console.log('No task ID found!');
    }
});

// Also update the task select when the project changes
const activityProjectSelect = document.getElementById('activityProject');
if (activityProjectSelect) {
    activityProjectSelect.addEventListener('change', populateTaskSelect);
}










