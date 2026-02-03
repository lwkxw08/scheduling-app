const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiService {
  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    const token = localStorage.getItem('token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers: {
        ...this.getHeaders(),
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'An error occurred' }));
      throw new Error(error.detail || 'An error occurred');
    }

    return response.json();
  }

  async register(email: string, password: string, fullName: string) {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
  }

  async login(email: string, password: string) {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  async getMicrosoftAuthUrl(redirectUri: string) {
    return this.request<{ auth_url: string }>(`/auth/microsoft/url?redirect_uri=${encodeURIComponent(redirectUri)}`);
  }

  async microsoftCallback(code: string, redirectUri: string) {
    return this.request('/auth/microsoft/callback', {
      method: 'POST',
      body: JSON.stringify({ code, redirect_uri: redirectUri }),
    });
  }

  async getCurrentUser() {
    return this.request('/auth/me');
  }

  async getProducts() {
    return this.request('/admin/products');
  }

  async createProduct(name: string, description?: string, expediteFee?: number, expediteContactEmails?: string[]) {
    return this.request('/admin/products', {
      method: 'POST',
      body: JSON.stringify({ name, description, expedite_fee: expediteFee, expedite_contact_emails: expediteContactEmails }),
    });
  }

  async updateProduct(id: number, name?: string, description?: string, expediteFee?: number, expediteContactEmails?: string[]) {
    return this.request(`/admin/products/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ name, description, expedite_fee: expediteFee, expedite_contact_emails: expediteContactEmails }),
    });
  }

  async deleteProduct(id: number) {
    return this.request(`/admin/products/${id}`, { method: 'DELETE' });
  }

  async getChangeTypes() {
    return this.request('/admin/change-types');
  }

  async createChangeType(name: string, description?: string, minimumNoticeHours?: number, cancellationNoticeHours?: number | null, amendmentNoticeHours?: number | null) {
    return this.request('/admin/change-types', {
      method: 'POST',
      body: JSON.stringify({ 
        name, 
        description, 
        minimum_notice_hours: minimumNoticeHours || 0,
        cancellation_notice_hours: cancellationNoticeHours,
        amendment_notice_hours: amendmentNoticeHours
      }),
    });
  }

  async updateChangeType(id: number, name: string, description?: string, minimumNoticeHours?: number, cancellationNoticeHours?: number | null, amendmentNoticeHours?: number | null) {
    return this.request(`/admin/change-types/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ 
        name, 
        description, 
        minimum_notice_hours: minimumNoticeHours,
        cancellation_notice_hours: cancellationNoticeHours,
        amendment_notice_hours: amendmentNoticeHours
      }),
    });
  }

  async deleteChangeType(id: number) {
    return this.request(`/admin/change-types/${id}`, { method: 'DELETE' });
  }

  async getEngineers() {
    return this.request('/admin/engineers');
  }

  async createEngineer(userId: number, calendarEmail: string, workingHoursStart?: string, workingHoursEnd?: string) {
    return this.request('/admin/engineers', {
      method: 'POST',
      body: JSON.stringify({
        user_id: userId,
        calendar_email: calendarEmail,
        working_hours_start: workingHoursStart || '09:00',
        working_hours_end: workingHoursEnd || '17:00',
      }),
    });
  }

  async updateEngineer(id: number, data: Record<string, any>) {
    const params = new URLSearchParams();
    Object.entries(data).forEach(([key, value]) => {
      if (value !== undefined) params.append(key, String(value));
    });
    return this.request(`/admin/engineers/${id}?${params.toString()}`, { method: 'PATCH' });
  }

  async getEngineerSkills(engineerId: number) {
    return this.request(`/admin/engineers/${engineerId}/skills`);
  }

  async addEngineerSkill(engineerId: number, productId: number, changeTypeId: number, proficiencyLevel?: number) {
    return this.request(`/admin/engineers/${engineerId}/skills`, {
      method: 'POST',
      body: JSON.stringify({
        engineer_id: engineerId,
        product_id: productId,
        change_type_id: changeTypeId,
        proficiency_level: proficiencyLevel || 1,
      }),
    });
  }

  async removeEngineerSkill(engineerId: number, skillId: number) {
    return this.request(`/admin/engineers/${engineerId}/skills/${skillId}`, { method: 'DELETE' });
  }

  async getCustomFields() {
    return this.request('/admin/custom-fields');
  }

  async createCustomField(data: { name: string; field_type: string; is_required?: boolean; options?: string[]; display_order?: number }) {
    return this.request('/admin/custom-fields', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateCustomField(id: number, data: { name: string; field_type: string; is_required?: boolean; options?: string[]; display_order?: number }) {
    return this.request(`/admin/custom-fields/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deleteCustomField(id: number) {
    return this.request(`/admin/custom-fields/${id}`, { method: 'DELETE' });
  }

  async getFees() {
    return this.request('/admin/fees');
  }

  async createFee(data: { 
    name: string; 
    fee_type: string; 
    amount: number; 
    description?: string;
    apply_mode?: string;
    product_ids?: number[];
    change_type_ids?: number[];
    apply_on_weekends?: boolean;
    apply_on_bank_holidays?: boolean;
    apply_outside_hours?: boolean;
    outside_hours_start?: string;
    outside_hours_end?: string;
  }) {
    return this.request('/admin/fees', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateFee(id: number, data: { 
    name?: string; 
    fee_type?: string; 
    amount?: number; 
    description?: string;
    apply_mode?: string;
    product_ids?: number[];
    change_type_ids?: number[];
    apply_on_weekends?: boolean;
    apply_on_bank_holidays?: boolean;
    apply_outside_hours?: boolean;
    outside_hours_start?: string;
    outside_hours_end?: string;
  }) {
    return this.request(`/admin/fees/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deleteFee(id: number) {
    return this.request(`/admin/fees/${id}`, { method: 'DELETE' });
  }

  async getSystemConfig() {
    return this.request('/admin/config');
  }

  async setSystemConfig(key: string, value: string, description?: string) {
    return this.request('/admin/config', {
      method: 'POST',
      body: JSON.stringify({ key, value, description }),
    });
  }

  async getDashboardStats() {
    return this.request('/admin/dashboard/stats');
  }

  async getAllUsers() {
    return this.request('/admin/users');
  }

  async updateUserRole(userId: number, role: string) {
    return this.request(`/admin/users/${userId}/role?role=${role}`, { method: 'PATCH' });
  }

  async checkAvailability(date: string, productId: number, changeTypeId: number, durationHours: number) {
    return this.request('/availability/check', {
      method: 'POST',
      body: JSON.stringify({
        date,
        product_id: productId,
        change_type_id: changeTypeId,
        duration_hours: durationHours,
      }),
    });
  }

  async getBookings() {
    return this.request('/bookings/');
  }

  async getBooking(id: number) {
    return this.request(`/bookings/${id}`);
  }

  async createBooking(data: {
    order_reference: string;
    customer_name: string;
    engineer_id: number;
    product_id: number;
    change_type_id: number;
    scheduled_date: string;
    duration_hours: number;
    custom_fields_data?: Record<string, any>;
    notes?: string;
    additional_emails?: string[];
    engineer_attachment_url?: string;
    customer_attachment_url?: string;
    is_expedited?: boolean;
  }) {
    return this.request('/bookings/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateBooking(id: number, data: {
    scheduled_date?: string;
    duration_hours?: number;
    notes?: string;
    custom_fields_data?: Record<string, any>;
    additional_emails?: string[];
    engineer_attachment_url?: string;
    customer_attachment_url?: string;
    engineer_id?: number;
  }) {
    return this.request(`/bookings/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async cancelBooking(id: number) {
    return this.request(`/bookings/${id}`, { method: 'DELETE' });
  }

  async getSetupStatus() {
    return this.request<{ has_admin: boolean; admin_count: number }>('/auth/setup/status');
  }

  async promoteToAdmin() {
    return this.request('/auth/setup/promote-to-admin', { method: 'POST' });
  }

  async getEngineerSchedules(engineerId: number) {
    return this.request(`/admin/engineers/${engineerId}/schedules`);
  }

  async updateEngineerSchedules(engineerId: number, schedules: Array<{
    day_of_week: number;
    is_working: boolean;
    start_time: string;
    end_time: string;
  }>) {
    return this.request(`/admin/engineers/${engineerId}/schedules`, {
      method: 'PUT',
      body: JSON.stringify({ schedules }),
    });
  }

  async createDefaultSchedules(engineerId: number) {
    return this.request(`/admin/engineers/${engineerId}/schedules/default`, { method: 'POST' });
  }

  async getTemplatePlaceholders() {
    return this.request<{ booking_fields: string[] }>('/admin/templates/placeholders');
  }

  async getEmailTemplates(templateType?: string) {
    const params = templateType ? `?template_type=${templateType}` : '';
    return this.request(`/admin/email-templates${params}`);
  }

  async getEmailTemplate(id: number) {
    return this.request(`/admin/email-templates/${id}`);
  }

  async createEmailTemplate(data: {
    name: string;
    template_type: string;
    subject: string;
    body_html: string;
    logo_url?: string;
    send_to_engineer?: boolean;
    send_to_customer?: boolean;
    additional_emails?: string[];
    is_default?: boolean;
  }) {
    return this.request('/admin/email-templates', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateEmailTemplate(id: number, data: {
    name: string;
    template_type: string;
    subject: string;
    body_html: string;
    logo_url?: string;
    send_to_engineer?: boolean;
    send_to_customer?: boolean;
    additional_emails?: string[];
    is_default?: boolean;
  }) {
    return this.request(`/admin/email-templates/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteEmailTemplate(id: number) {
    return this.request(`/admin/email-templates/${id}`, { method: 'DELETE' });
  }

  async getCalendarTemplates(templateType?: string) {
    const params = templateType ? `?template_type=${templateType}` : '';
    return this.request(`/admin/calendar-templates${params}`);
  }

  async getCalendarTemplate(id: number) {
    return this.request(`/admin/calendar-templates/${id}`);
  }

  async createCalendarTemplate(data: {
    name: string;
    template_type: string;
    event_title: string;
    event_body?: string;
    include_customer_as_attendee?: boolean;
    additional_attendees?: string[];
    is_default?: boolean;
  }) {
    return this.request('/admin/calendar-templates', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateCalendarTemplate(id: number, data: {
    name: string;
    template_type: string;
    event_title: string;
    event_body?: string;
    include_customer_as_attendee?: boolean;
    additional_attendees?: string[];
    is_default?: boolean;
  }) {
    return this.request(`/admin/calendar-templates/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteCalendarTemplate(id: number) {
    return this.request(`/admin/calendar-templates/${id}`, { method: 'DELETE' });
  }

  // Roster Pattern Methods
  async getRosterPatterns() {
    return this.request('/admin/roster-patterns');
  }

  async getRosterPattern(id: number) {
    return this.request(`/admin/roster-patterns/${id}`);
  }

  async createRosterPattern(data: {
    name: string;
    description?: string;
    phases: Array<{
      phase_order: number;
      name?: string;
      days_on: number;
      days_off: number;
      start_time: string;
      end_time: string;
      repeat_weeks?: number;
    }>;
  }) {
    return this.request('/admin/roster-patterns', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateRosterPattern(id: number, data: {
    name?: string;
    description?: string;
    phases?: Array<{
      phase_order: number;
      name?: string;
      days_on: number;
      days_off: number;
      start_time: string;
      end_time: string;
      repeat_weeks?: number;
    }>;
  }) {
    return this.request(`/admin/roster-patterns/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteRosterPattern(id: number) {
    return this.request(`/admin/roster-patterns/${id}`, { method: 'DELETE' });
  }

  // Engineer Roster Assignment Methods
  async getEngineerRosterAssignment(engineerId: number) {
    return this.request(`/admin/engineers/${engineerId}/roster-assignment`);
  }

  async assignRosterToEngineer(engineerId: number, data: {
    pattern_id: number;
    start_date: string;
    end_date?: string;
    is_repeating?: boolean;
  }) {
    return this.request(`/admin/engineers/${engineerId}/roster-assignment`, {
      method: 'POST',
      body: JSON.stringify({
        engineer_id: engineerId,
        ...data,
      }),
    });
  }

  async removeEngineerRosterAssignment(engineerId: number) {
    return this.request(`/admin/engineers/${engineerId}/roster-assignment`, { method: 'DELETE' });
  }

  async getAllRosterAssignments() {
    return this.request('/admin/roster-assignments');
  }

  async uploadFile(file: File, fileType: 'logo' | 'attachment' = 'attachment'): Promise<{
    filename: string;
    original_filename: string;
    file_type: string;
    url: string;
  }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('file_type', fileType);

    const token = localStorage.getItem('token');
    const headers: HeadersInit = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_URL}/admin/upload`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail || 'Upload failed');
    }

    return response.json();
  }

  getFileUrl(relativePath: string): string {
    if (relativePath.startsWith('http')) {
      return relativePath;
    }
    return `${API_URL}${relativePath}`;
  }

  // Expedite Request Methods
  async createExpediteRequest(data: {
    product_id: number;
    change_type_id: number;
    order_reference: string;
    customer_name: string;
    requested_date: string;
    duration_hours: number;
    custom_fields_data?: Record<string, any>;
    notes?: string;
    additional_emails?: string[];
    engineer_attachment_url?: string;
    customer_attachment_url?: string;
    fee_acknowledged: boolean;
  }) {
    return this.request('/bookings/expedite-request', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getMyExpediteRequests() {
    return this.request('/bookings/expedite-requests/my');
  }

  async getProductExpediteFee(productId: number) {
    return this.request<{ product_id: number; product_name: string; expedite_fee: number }>(
      `/bookings/product/${productId}/expedite-fee`
    );
  }

  async previewApplicableFees(data: {
    product_id: number;
    change_type_id: number;
    scheduled_date: string;
    duration_hours: number;
  }) {
    const params = new URLSearchParams();
    params.append('product_id', data.product_id.toString());
    params.append('change_type_id', data.change_type_id.toString());
    params.append('scheduled_date', data.scheduled_date);
    params.append('duration_hours', data.duration_hours.toString());
    return this.request<{
      fees: Array<{
        fee_id: number | null;
        name: string;
        fee_type: string;
        amount: number;
        requires_approval: boolean;
        is_per_hour: boolean;
      }>;
      indicator_fees: Array<{
        fee_id: number | null;
        name: string;
        fee_type: string;
        amount: number;
        requires_approval: boolean;
        is_indicator: boolean;
        indicator_reason: string;
      }>;
      total: number;
      is_expedite_booking: boolean;
      hours_until_booking: number;
      minimum_notice_hours: number;
    }>(`/bookings/preview-fees?${params.toString()}`, { method: 'POST' });
  }

  // Admin Expedite Request Methods
  async getExpediteRequests(statusFilter?: string) {
    const params = statusFilter ? `?status_filter=${statusFilter}` : '';
    return this.request(`/admin/expedite-requests${params}`);
  }

  async getExpediteRequest(requestId: number) {
    return this.request(`/admin/expedite-requests/${requestId}`);
  }

  async approveExpediteRequest(requestId: number, data: {
    assigned_engineer_id: number;
    scheduled_date: string;
    admin_notes?: string;
  }) {
    return this.request(`/admin/expedite-requests/${requestId}/approve`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async rejectExpediteRequest(requestId: number, data: { admin_notes?: string }) {
    return this.request(`/admin/expedite-requests/${requestId}/reject`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Reporting endpoints
    async getBookingsReport(filters: {
      start_date?: string;
      end_date?: string;
      status?: string;
      product_id?: number;
      engineer_id?: number;
    } = {}) {
      const params = new URLSearchParams();
      if (filters.start_date) params.append('start_date', filters.start_date);
      if (filters.end_date) params.append('end_date', filters.end_date);
      if (filters.status) params.append('status', filters.status);
      if (filters.product_id) params.append('product_id', filters.product_id.toString());
      if (filters.engineer_id) params.append('engineer_id', filters.engineer_id.toString());
      return this.request(`/admin/reports/bookings?${params.toString()}`);
    }

    async getFullDataExport(filters: {
      start_date?: string;
      end_date?: string;
      status?: string;
      product_id?: number;
      engineer_id?: number;
    } = {}) {
      const params = new URLSearchParams();
      if (filters.start_date) params.append('start_date', filters.start_date);
      if (filters.end_date) params.append('end_date', filters.end_date);
      if (filters.status) params.append('status', filters.status);
      if (filters.product_id) params.append('product_id', filters.product_id.toString());
      if (filters.engineer_id) params.append('engineer_id', filters.engineer_id.toString());
      return this.request(`/admin/reports/full-data-export?${params.toString()}`);
    }

    async getEngineersUtilizationReport(filters: { start_date?: string; end_date?: string } = {}) {
    const params = new URLSearchParams();
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);
    return this.request(`/admin/reports/engineers-utilization?${params.toString()}`);
  }

  async getProductsSummaryReport(filters: { start_date?: string; end_date?: string } = {}) {
    const params = new URLSearchParams();
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);
    return this.request(`/admin/reports/products-summary?${params.toString()}`);
  }

  async getExpediteRequestsSummaryReport(filters: { start_date?: string; end_date?: string } = {}) {
    const params = new URLSearchParams();
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);
    return this.request(`/admin/reports/expedite-requests-summary?${params.toString()}`);
  }

  async getRevenueSummaryReport(filters: { start_date?: string; end_date?: string } = {}) {
    const params = new URLSearchParams();
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);
    return this.request(`/admin/reports/revenue-summary?${params.toString()}`);
  }

  async getFeesByBookingReport(filters: {
    start_date?: string;
    end_date?: string;
    status?: string;
    product_id?: number;
  } = {}) {
    const params = new URLSearchParams();
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);
    if (filters.status) params.append('status', filters.status);
    if (filters.product_id) params.append('product_id', filters.product_id.toString());
    return this.request(`/admin/reports/fees-by-booking?${params.toString()}`);
  }

  // Engineer Dashboard Methods
  async getEngineerProfile() {
    return this.request('/engineer/profile');
  }

  async getEngineerDashboardStats() {
    return this.request('/engineer/dashboard/stats');
  }

  async getEngineerBookings(upcomingOnly: boolean = false) {
    const params = upcomingOnly ? '?upcoming_only=true' : '';
    return this.request(`/engineer/bookings${params}`);
  }

  async getEngineerBookingDetails(bookingId: number) {
    return this.request(`/engineer/bookings/${bookingId}`);
  }

  async updateBookingStatus(bookingId: number, data: {
    new_status: string;
    notes?: string;
    issue_reported?: boolean;
    issue_description?: string;
  }) {
    return this.request(`/engineer/bookings/${bookingId}/status`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getEngineerUnavailability() {
    return this.request('/engineer/unavailability');
  }

  async createEngineerUnavailability(data: {
    start_datetime: string;
    end_datetime: string;
    reason?: string;
    is_all_day?: boolean;
  }) {
    return this.request('/engineer/unavailability', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteEngineerUnavailability(entryId: number) {
    return this.request(`/engineer/unavailability/${entryId}`, { method: 'DELETE' });
  }

  // Admin Unavailability Management
  async getAdminEngineerUnavailability(engineerId: number) {
    return this.request(`/admin/engineers/${engineerId}/unavailability`);
  }

  async createAdminEngineerUnavailability(engineerId: number, data: {
    start_datetime: string;
    end_datetime: string;
    reason?: string;
    is_all_day?: boolean;
  }) {
    return this.request(`/admin/engineers/${engineerId}/unavailability`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteAdminUnavailability(unavailabilityId: number) {
    return this.request(`/admin/unavailability/${unavailabilityId}`, { method: 'DELETE' });
  }

  async getAllUnavailability() {
    return this.request('/admin/all-unavailability');
  }

  // Email Preview and SMTP Methods
  async previewEmailTemplate(templateId: number) {
    return this.request<{
      subject: string;
      body_html: string;
      logo_url?: string;
      send_to_engineer: boolean;
      send_to_customer: boolean;
      additional_emails?: string[];
    }>(`/admin/email-templates/${templateId}/preview`, { method: 'POST' });
  }

  async previewCustomEmail(subject: string, bodyHtml: string, logoUrl?: string) {
    const params = new URLSearchParams();
    params.append('subject', subject);
    params.append('body_html', bodyHtml);
    if (logoUrl) params.append('logo_url', logoUrl);
    return this.request<{ subject: string; body_html: string }>(`/admin/email-templates/preview-custom?${params.toString()}`, { method: 'POST' });
  }

  async testSmtpConnection() {
    return this.request<{ success: boolean; message: string }>('/admin/smtp/test', { method: 'POST' });
  }

  async sendTestEmail(toEmail: string) {
    return this.request<{ success: boolean; message: string }>(`/admin/smtp/send-test-email?to_email=${encodeURIComponent(toEmail)}`, { method: 'POST' });
  }

  async getBookingSettings() {
    return this.request<{ booking_advance_limit_days: number }>('/bookings/booking-settings');
  }

  // Booking Fees
  async getBookingFees(bookingId: number) {
    return this.request<any[]>(`/admin/bookings/${bookingId}/fees`);
  }

    async getPendingFeeApprovals() {
      return this.request<any[]>('/admin/fees/pending-approvals');
    }

  async waiveBookingFee(bookingFeeId: number, reason?: string) {
    const params = reason ? `?reason=${encodeURIComponent(reason)}` : '';
    return this.request<any>(`/admin/booking-fees/${bookingFeeId}/waive${params}`, { method: 'POST' });
  }

  async approveBookingFee(bookingFeeId: number) {
    return this.request<any>(`/admin/booking-fees/${bookingFeeId}/approve`, { method: 'POST' });
  }

  async removeBookingFee(bookingFeeId: number) {
    return this.request<any>(`/admin/booking-fees/${bookingFeeId}`, { method: 'DELETE' });
  }

  // Email Rules
  async getEmailRules() {
    return this.request<any[]>('/admin/email-rules');
  }

  async getEmailRule(ruleId: number) {
    return this.request<any>(`/admin/email-rules/${ruleId}`);
  }

  async createEmailRule(data: {
    name: string;
    description?: string;
    trigger_type: string;
    trigger_hours?: number;
    condition_status?: string;
    email_template_id: number;
    recipient_types: string[];
    additional_emails?: string[];
    is_active?: boolean;
  }) {
    return this.request<any>('/admin/email-rules', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateEmailRule(ruleId: number, data: {
    name?: string;
    description?: string;
    trigger_type?: string;
    trigger_hours?: number;
    condition_status?: string;
    email_template_id?: number;
    recipient_types?: string[];
    additional_emails?: string[];
    is_active?: boolean;
  }) {
    return this.request<any>(`/admin/email-rules/${ruleId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteEmailRule(ruleId: number) {
    return this.request<any>(`/admin/email-rules/${ruleId}`, { method: 'DELETE' });
  }

  async toggleEmailRule(ruleId: number) {
    return this.request<any>(`/admin/email-rules/${ruleId}/toggle`, { method: 'POST' });
  }

  async getEmailRuleLogs(ruleId: number) {
    return this.request<any[]>(`/admin/email-rules/${ruleId}/logs`);
  }

  async processEmailRules() {
    return this.request<any>('/admin/email-rules/process', { method: 'POST' });
  }

  async permanentlyDeleteBooking(bookingId: number) {
    return this.request<any>(`/admin/bookings/${bookingId}/permanent`, { method: 'DELETE' });
  }

  async getBankHolidays() {
    return this.request<any[]>('/admin/bank-holidays');
  }

  async createBankHoliday(data: { name: string; date: string }) {
    return this.request<any>('/admin/bank-holidays', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteBankHoliday(id: number) {
    return this.request<any>(`/admin/bank-holidays/${id}`, { method: 'DELETE' });
  }

  async deleteUser(userId: number) {
    return this.request<any>(`/admin/users/${userId}`, { method: 'DELETE' });
  }

  async getUserActivityReport() {
    return this.request<any[]>('/admin/reports/user-activity');
  }

  async getOpenIssues(includeResolved: boolean = false) {
    return this.request<any[]>(`/admin/issues?include_resolved=${includeResolved}`);
  }

  async getOpenIssuesCount() {
    return this.request<{ count: number }>('/admin/issues/count');
  }

  async resolveIssue(bookingId: number) {
    return this.request<any>(`/admin/issues/${bookingId}/resolve`, { method: 'PATCH' });
  }

  async reopenIssue(bookingId: number) {
    return this.request<any>(`/admin/issues/${bookingId}/reopen`, { method: 'PATCH' });
  }
}

export const api = new ApiService();
