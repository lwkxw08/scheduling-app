export interface User {
  id: number;
  email: string;
  full_name: string;
  role: 'user' | 'engineer' | 'admin';
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Product {
  id: number;
  name: string;
  description: string | null;
  expedite_fee: number;
  expedite_contact_emails: string[] | null;
  is_active: boolean;
  created_at: string;
}

export interface ChangeType {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Engineer {
  id: number;
  user_id: number;
  calendar_email: string;
  is_available: boolean;
  working_hours_start: string;
  working_hours_end: string;
  user?: User;
}

export interface EngineerSkill {
  id: number;
  engineer_id: number;
  product_id: number;
  change_type_id: number;
  proficiency_level: number;
  product?: Product;
  change_type?: ChangeType;
}

export interface CustomField {
  id: number;
  name: string;
  field_type: string;
  is_required: boolean;
  options: string[] | null;
  display_order: number;
  is_active: boolean;
  created_at: string;
}

export interface Booking {
  id: number;
  order_reference: string;
  customer_name: string;
  booker_id: number;
  engineer_id: number;
  product_id: number;
  change_type_id: number;
  scheduled_date: string;
  duration_hours: number;
  status: 'pending' | 'confirmed' | 'cancelled' | 'completed';
  custom_fields_data: Record<string, any> | null;
  notes: string | null;
  additional_emails: string[] | null;
  engineer_attachment_url: string | null;
  customer_attachment_url: string | null;
  cancellation_fee: number;
  expedite_fee: number;
  created_at: string;
  updated_at: string;
  engineer?: Engineer;
  product?: Product;
  change_type?: ChangeType;
}

export interface TimeSlot {
  start_time: string;
  end_time: string;
  is_available: boolean;
}

export interface EngineerAvailability {
  engineer_id: number;
  engineer_name: string;
  calendar_email: string;
  slots: TimeSlot[];
}

export interface AvailabilityResponse {
  date: string;
  engineers: EngineerAvailability[];
}

export interface Fee {
  id: number;
  name: string;
  fee_type: string;
  amount: number;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface SystemConfig {
  id: number;
  key: string;
  value: string;
  description: string | null;
  updated_at: string;
}

export interface DashboardStats {
  total_bookings: number;
  pending_bookings: number;
  confirmed_bookings: number;
  total_engineers: number;
  available_engineers: number;
  pending_expedite_requests: number;
}

export type TemplateType = 'confirmation' | 'amendment' | 'cancellation' | 'reminder';

export interface EmailTemplate {
  id: number;
  name: string;
  template_type: TemplateType;
  subject: string;
  body_html: string;
  logo_url: string | null;
  send_to_engineer: boolean;
  send_to_customer: boolean;
  additional_emails: string[] | null;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface CalendarEventTemplate {
  id: number;
  name: string;
  template_type: TemplateType;
  event_title: string;
  event_body: string | null;
  include_customer_as_attendee: boolean;
  additional_attendees: string[] | null;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface RosterPhase {
  id: number;
  pattern_id: number;
  phase_order: number;
  name: string | null;
  days_on: number;
  days_off: number;
  start_time: string;
  end_time: string;
  repeat_weeks: number | null;
  created_at: string;
}

export interface RosterPattern {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  phases: RosterPhase[];
  created_at: string;
  updated_at: string;
}

export interface RosterPatternListItem {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  phase_count: number;
  created_at: string;
}

export interface EngineerRosterAssignment {
  id: number;
  engineer_id: number;
  pattern_id: number;
  start_date: string;
  end_date: string | null;
  is_repeating: boolean;
  is_active: boolean;
  pattern?: RosterPattern;
  created_at: string;
  updated_at: string;
}

export interface EngineerUnavailability {
  id: number;
  engineer_id: number;
  start_datetime: string;
  end_datetime: string;
  reason: string | null;
  created_by_id: number;
  is_all_day: boolean;
  created_at: string;
  updated_at: string;
  created_by?: User;
  engineer?: Engineer;
}

export interface BookingStatusUpdate {
  id: number;
  booking_id: number;
  updated_by_id: number;
  previous_status: string | null;
  new_status: string;
  notes: string | null;
  issue_reported: boolean;
  issue_description: string | null;
  created_at: string;
  updated_by?: User;
}

export interface EngineerDashboardStats {
  total_bookings: number;
  upcoming_bookings: number;
  completed_bookings: number;
  pending_bookings: number;
  issues_reported: number;
}

export type ExpediteRequestStatus = 'pending' | 'approved' | 'rejected';

export interface ExpediteRequest {
  id: number;
  requester_id: number;
  product_id: number;
  change_type_id: number;
  order_reference: string;
  customer_name: string;
  requested_date: string;
  duration_hours: number;
  custom_fields_data: Record<string, any> | null;
  notes: string | null;
  additional_emails: string[] | null;
  engineer_attachment_url: string | null;
  customer_attachment_url: string | null;
  expedite_fee: number;
  fee_acknowledged: boolean;
  status: ExpediteRequestStatus;
  admin_notes: string | null;
  assigned_engineer_id: number | null;
  resulting_booking_id: number | null;
  created_at: string;
  updated_at: string;
  requester?: User;
  product?: Product;
  change_type?: ChangeType;
  assigned_engineer?: Engineer;
}
