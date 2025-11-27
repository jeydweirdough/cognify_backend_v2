# Cognify API Routes - Frontend Integration Guide

## Base Configuration

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json'
  }
});

// Token interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Refresh token on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refreshToken = localStorage.getItem('refreshToken');
      const { data } = await axios.post('/auth/refresh', { refresh_token: refreshToken });
      localStorage.setItem('token', data.token);
      localStorage.setItem('refreshToken', data.refresh_token);
      error.config.headers.Authorization = `Bearer ${data.token}`;
      return axios(error.config);
    }
    return Promise.reject(error);
  }
);
```

---

## Authentication (`/auth`)

### Sign Up
```javascript
await api.post('/auth/signup', {
  email: 'student@cvsu.edu.ph',
  password: 'Password123!',
  first_name: 'Juan',
  last_name: 'Dela Cruz'
});
```

### Login
```javascript
const { data } = await api.post('/auth/login', {
  email: 'student@cvsu.edu.ph',
  password: 'Password123!'
});
localStorage.setItem('token', data.token);
localStorage.setItem('refreshToken', data.refresh_token);
localStorage.setItem('uid', data.uid);
```

### Refresh Token
```javascript
const { data } = await api.post('/auth/refresh', {
  refresh_token: localStorage.getItem('refreshToken')
});
localStorage.setItem('token', data.token);
localStorage.setItem('refreshToken', data.refresh_token);
```

### Logout
```javascript
await api.post('/auth/logout');
localStorage.clear();
```

---

## Profiles (`/profiles`)

### Get My Profile
```javascript
const { data } = await api.get('/profiles/me');
// data.role: "student" | "faculty_member" | "admin"
// data.data: role-specific profile data
```

### Update My Profile
```javascript
await api.put('/profiles/me', {
  first_name: 'Juan',
  profile_picture: 'https://drive.google.com/...'
});
```

### Get My Permissions
```javascript
const { data } = await api.get('/profiles/me/permissions');
// data.permissions: { can_view_own_profile, can_view_other_students, ... }
```

### View User Profile
```javascript
const { data } = await api.get(`/profiles/user/${userId}`);
// Faculty can view students; Admin can view all
```

### List Students (Faculty/Admin)
```javascript
const { data } = await api.get('/profiles/students', {
  params: { skip: 0, limit: 50 }
});
// data.students: [{ id, email, first_name, ... }]
```

### List Faculty (Admin Only)
```javascript
const { data } = await api.get('/profiles/faculty', {
  params: { skip: 0, limit: 50 }
});
```

### Search Users
```javascript
const { data } = await api.get('/profiles/search', {
  params: { query: 'maria', role_filter: 'student' }
});
// data.results: filtered users
```

### Student Performance
```javascript
const { data } = await api.get(`/profiles/student/${studentId}/performance`);
// data: { readiness, timeliness, behavior_profile, progress_reports, ... }
```

### Student Activity
```javascript
const { data } = await api.get(`/profiles/student/${studentId}/activity`, {
  params: { limit: 20 }
});
// data: { recent_study_sessions, recent_assessments, summary }
```

### System Overview (Admin)
```javascript
const { data } = await api.get('/profiles/admin/system-overview');
// data.statistics: { total_users, students, faculty, pending_verifications, ... }
```

---

## Admin Management (`/admin`)

### Whitelist User
```javascript
await api.post('/admin/whitelist-user', null, {
  params: { email: 'newuser@cvsu.edu.ph', role: 'student' }
});
```

### Get Whitelist
```javascript
const { data } = await api.get('/admin/whitelist', {
  params: { is_registered: false }
});
// data.users: [{ email, assigned_role, is_registered, ... }]
```

### Remove from Whitelist
```javascript
await api.delete(`/admin/whitelist/${email}`);
```

### Get Pending Verifications
```javascript
const { data } = await api.get('/admin/users/pending-verification');
```

### Verify User
```javascript
await api.post(`/admin/users/${userId}/verify`);
```

### Deactivate User
```javascript
await api.post(`/admin/users/${userId}/deactivate`, null, {
  params: { reason: 'Policy violation' }
});
```

### User Statistics
```javascript
const { data } = await api.get('/admin/users/statistics');
// data: { total_users, by_role, verified_users, ... }
```

### Create Announcement
```javascript
await api.post('/admin/announcements', {
  title: 'System Maintenance',
  content: 'Scheduled downtime...',
  target_roles: ['student', 'faculty'],
  is_global: false
});
```

### Get Announcements
```javascript
const { data } = await api.get('/admin/announcements', {
  params: { skip: 0, limit: 20 }
});
```

### Update Announcement
```javascript
await api.put(`/admin/announcements/${announcementId}`, {
  title: 'Updated Title',
  content: 'Updated content'
});
```

### Delete Announcement
```javascript
await api.delete(`/admin/announcements/${announcementId}`);
```

### Get Unverified Questions
```javascript
const { data } = await api.get('/admin/pending-questions');
```

### Verify Question
```javascript
await api.post(`/admin/verify-question/${questionId}`);
```

### Reject Question
```javascript
await api.post(`/admin/reject-question/${questionId}`, null, {
  params: { reason: 'Does not meet standards' }
});
```

### Get Unverified Assessments
```javascript
const { data } = await api.get('/admin/pending-assessments');
```

### Verify Assessment
```javascript
await api.post(`/admin/verify-assessment/${assessmentId}`);
```

### Get Unverified Modules
```javascript
const { data } = await api.get('/admin/pending-modules');
```

### Verify Module
```javascript
await api.post(`/admin/verify-module/${subjectId}/${topicId}`);
```

### System Health
```javascript
const { data } = await api.get('/admin/system/health');
```

---

## Table of Specifications (`/tos`)

### Upload TOS PDF (Admin)
```javascript
const formData = new FormData();
formData.append('file', pdfFile);

const { data } = await api.post('/tos/upload-tos', formData, {
  headers: { 'Content-Type': 'multipart/form-data' }
});
// data: SubjectSchema with extracted topics and competencies
```

---

## Modules (`/modules`)

### Upload Module with AI Categorization
```javascript
const formData = new FormData();
formData.append('file', pdfFile);
formData.append('subject_id', subjectId);

const { data } = await api.post('/modules/upload-smart', formData, {
  headers: { 'Content-Type': 'multipart/form-data' }
});
// data: { matched_topic, ai_reasoning, file_url }
```

---

## Questions (`/questions`)

### Create Question
```javascript
await api.post('/questions', {
  text: 'What is the ID in Freud\'s theory?',
  type: 'multiple_choice',
  choices: ['Pleasure principle', 'Reality principle', 'Moral principle', 'Conscious principle'],
  correct_answers: 'Pleasure principle',
  competency_id: 'comp_123',
  bloom_taxonomy: 'remembering',
  difficulty_level: 'Easy'
});
```

### Bulk Create Questions
```javascript
await api.post('/questions/bulk', {
  questions: [{ text: '...', type: '...', ... }],
  validate_distribution: true
});
```

### Get Questions (Filtered)
```javascript
const { data } = await api.get('/questions', {
  params: {
    competency_id: 'comp_123',
    bloom_taxonomy: 'remembering',
    difficulty_level: 'Easy',
    is_verified: true,
    skip: 0,
    limit: 50
  }
});
```

### Get Question by ID
```javascript
const { data } = await api.get(`/questions/${questionId}`);
```

### Update Question
```javascript
await api.put(`/questions/${questionId}`, {
  text: 'Updated question text',
  difficulty_level: 'Moderate'
});
```

### Delete Question
```javascript
await api.delete(`/questions/${questionId}`);
```

### Verify Question (Faculty)
```javascript
await api.post(`/questions/${questionId}/verify`);
```

### Get Competency Distribution
```javascript
const { data } = await api.get(`/questions/competency/${competencyId}/distribution`);
// data: { total_questions, by_difficulty, by_taxonomy, board_exam_compliance }
```

### Get Validation Rules
```javascript
const { data } = await api.get('/questions/validation-rules');
// data: { type_to_taxonomy, difficulty_to_taxonomy, ... }
```

### Get Question Template
```javascript
const { data } = await api.get(`/questions/templates/${questionType}`);
// data: { structure, example, tips }
```

### Validate Question
```javascript
const { data } = await api.post('/questions/validate', {
  text: 'Question text',
  type: 'multiple_choice',
  choices: ['A', 'B', 'C', 'D'],
  correct_answers: 'A',
  bloom_taxonomy: 'remembering',
  difficulty_level: 'Easy'
});
// data: { is_valid, message, warnings/errors }
```

---

## Assessments (`/assessments`)

### Generate Assessment
```javascript
await api.post('/assessments/generate', {
  blueprint: {
    subject_id: 'subj_123',
    target_topics: ['topic1', 'topic2'],
    total_items: 50,
    easy_percentage: 0.30,
    moderate_percentage: 0.40,
    difficult_percentage: 0.30
  },
  title: 'Midterm Exam',
  assessment_type: 'quiz'
});
```

---

## Student Progress (`/student`)

### Get Student Profile
```javascript
const { data } = await api.get(`/student/profile/${userId}`);
```

### Analyze Readiness
```javascript
const { data } = await api.post(`/student/analyze-readiness/${userId}`);
// data: { new_readiness_level, ai_confidence }
```

### Start Study Session
```javascript
const { data } = await api.post('/student/session/start', {
  resource_id: 'module_123',
  resource_type: 'module'
});
// data.session_id: use for updates
```

### Update Study Session
```javascript
await api.post(`/student/session/update/${sessionId}`, {
  interruptions: 2,
  idle_time_seconds: 120,
  is_finished: true
});
```

### Get Session History
```javascript
const { data } = await api.get(`/student/session/history/${userId}`, {
  params: { limit: 50 }
});
```

### Get Behavior Analysis
```javascript
const { data } = await api.get(`/student/behavior-analysis/${userId}`);
// data: { reading_pattern, study_time_preferences, focus_metrics, ... }
```

### Get Adaptive Content Strategy
```javascript
const { data } = await api.get(`/student/adaptive-content/${userId}`, {
  params: { subject_id: 'subj_123' }
});
// data: { content_strategy, personalized_tips }
```

### Get My Announcements
```javascript
const { data } = await api.get('/student/announcements');
```

### Mark Announcement as Read
```javascript
await api.post(`/student/announcements/${announcementId}/read`);
```

### Get Notifications
```javascript
const { data } = await api.get('/student/notifications', {
  params: { unread_only: true }
});
```

### Mark Notification as Read
```javascript
await api.post(`/student/notifications/${notificationId}/read`);
```

### Mark All Notifications as Read
```javascript
await api.post('/student/notifications/read-all');
```

---

## Analytics (`/analytics`)

### Get Passing Rate
```javascript
const { data } = await api.get('/analytics/passing-rate', {
  params: { subject_id: 'subj_123', assessment_id: 'assess_123' }
});
// data: { passing_rate, average_score, total_submissions, ... }
```

### Get Passing Probability
```javascript
const { data } = await api.get(`/analytics/student/${userId}/passing-probability`, {
  params: { subject_id: 'subj_123' }
});
// data: { passing_probability, risk_level, recommendation }
```

### Get Student Weaknesses
```javascript
const { data } = await api.get(`/analytics/student/${userId}/weaknesses`, {
  params: { subject_id: 'subj_123' }
});
// data: { weaknesses: [...], recommendations: [...] }
```

### Get Study Recommendations
```javascript
const { data } = await api.get(`/analytics/student/${userId}/recommendations`, {
  params: { subject_id: 'subj_123' }
});
```

### Get Subject Analytics
```javascript
const { data } = await api.get(`/analytics/subject/${subjectId}/overview`);
// data: { passing_statistics, difficult_topics, engagement_metrics, ... }
```

### Teacher Dashboard
```javascript
const { data } = await api.get('/analytics/dashboard/teacher');
```

### Admin Dashboard
```javascript
const { data } = await api.get('/analytics/dashboard/admin');
```

---

## Error Handling

```javascript
try {
  await api.post('/some/endpoint', data);
} catch (error) {
  if (error.response) {
    // 400, 401, 403, 404, 500
    console.error(error.response.status, error.response.data.detail);
  } else if (error.request) {
    // Network error
    console.error('Network error');
  }
}
```

---

## Common Patterns

### File Upload
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('subject_id', subjectId);

await api.post('/endpoint', formData, {
  headers: { 'Content-Type': 'multipart/form-data' }
});
```

### Pagination
```javascript
const loadMore = async (page = 0, limit = 50) => {
  const { data } = await api.get('/endpoint', {
    params: { skip: page * limit, limit }
  });
  return data;
};
```

### Search with Debounce
```javascript
const searchUsers = debounce(async (query) => {
  if (query.length < 2) return;
  const { data } = await api.get('/profiles/search', {
    params: { query }
  });
  setResults(data.results);
}, 500);
```

### Conditional Rendering by Role
```javascript
const { data: permissions } = await api.get('/profiles/me/permissions');

{permissions.can_view_all_users_list && (
  <button onClick={() => navigate('/students')}>
    View All Students
  </button>
)}
```

---

## Environment Variables

```env
REACT_APP_API_URL=http://localhost:8000
```

```javascript
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL
});
```
