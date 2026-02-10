import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Calendar, Clock, CheckCircle, AlertCircle, XCircle, Plus, Trash2, ArrowLeft } from 'lucide-react';
import type { Booking, EngineerDashboardStats, EngineerUnavailability } from '@/types';

export default function EngineerDashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<EngineerDashboardStats | null>(null);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [unavailability, setUnavailability] = useState<EngineerUnavailability[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('bookings');
  const [showUpcomingOnly, setShowUpcomingOnly] = useState(true);
  
  // Gantt chart state
  const [ganttDate, setGanttDate] = useState(() => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  });

  // Status update dialog
  const [statusDialogOpen, setStatusDialogOpen] = useState(false);
  const [selectedBooking, setSelectedBooking] = useState<Booking | null>(null);
  const [newStatus, setNewStatus] = useState('');
  const [statusNotes, setStatusNotes] = useState('');
  const [issueReported, setIssueReported] = useState(false);
  const [issueDescription, setIssueDescription] = useState('');
  const [statusUpdating, setStatusUpdating] = useState(false);

  // Unavailability dialog
  const [unavailabilityDialogOpen, setUnavailabilityDialogOpen] = useState(false);
  const [unavailabilityStartDate, setUnavailabilityStartDate] = useState('');
  const [unavailabilityStartTime, setUnavailabilityStartTime] = useState('09:00');
  const [unavailabilityEndDate, setUnavailabilityEndDate] = useState('');
  const [unavailabilityEndTime, setUnavailabilityEndTime] = useState('17:00');
  const [unavailabilityReason, setUnavailabilityReason] = useState('');
  const [unavailabilityIsAllDay, setUnavailabilityIsAllDay] = useState(false);
  const [unavailabilityCreating, setUnavailabilityCreating] = useState(false);

  useEffect(() => {
    if (user?.role !== 'engineer' && user?.role !== 'admin') {
      navigate('/dashboard');
      return;
    }
    loadData();
  }, [user, navigate]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [statsData, bookingsData, unavailabilityData] = await Promise.all([
        api.getEngineerDashboardStats(),
        api.getEngineerBookings(showUpcomingOnly),
        api.getEngineerUnavailability(),
      ]);
      setStats(statsData as EngineerDashboardStats);
      setBookings(bookingsData as Booking[]);
      setUnavailability(unavailabilityData as EngineerUnavailability[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadBookings = async () => {
    try {
      const bookingsData = await api.getEngineerBookings(showUpcomingOnly);
      setBookings(bookingsData as Booking[]);
    } catch (err) {
      console.error('Failed to load bookings:', err);
    }
  };

  useEffect(() => {
    if (!loading) {
      loadBookings();
    }
  }, [showUpcomingOnly]);

  const openStatusDialog = (booking: Booking) => {
    setSelectedBooking(booking);
    setNewStatus(booking.status);
    setStatusNotes('');
    setIssueReported(false);
    setIssueDescription('');
    setStatusDialogOpen(true);
  };

  const handleStatusUpdate = async () => {
    if (!selectedBooking) return;
    
    try {
      setStatusUpdating(true);
      await api.updateBookingStatus(selectedBooking.id, {
        new_status: newStatus,
        notes: statusNotes || undefined,
        issue_reported: issueReported,
        issue_description: issueReported ? issueDescription : undefined,
      });
      setStatusDialogOpen(false);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update status');
    } finally {
      setStatusUpdating(false);
    }
  };

  const openUnavailabilityDialog = () => {
    const today = new Date().toISOString().split('T')[0];
    setUnavailabilityStartDate(today);
    setUnavailabilityEndDate(today);
    setUnavailabilityStartTime('09:00');
    setUnavailabilityEndTime('17:00');
    setUnavailabilityReason('');
    setUnavailabilityIsAllDay(false);
    setUnavailabilityDialogOpen(true);
  };

  const handleCreateUnavailability = async () => {
    try {
      setUnavailabilityCreating(true);
      
      let startDatetime: string;
      let endDatetime: string;
      
      if (unavailabilityIsAllDay) {
        startDatetime = `${unavailabilityStartDate}T00:00:00`;
        endDatetime = `${unavailabilityEndDate}T23:59:59`;
      } else {
        startDatetime = `${unavailabilityStartDate}T${unavailabilityStartTime}:00`;
        endDatetime = `${unavailabilityEndDate}T${unavailabilityEndTime}:00`;
      }
      
      await api.createEngineerUnavailability({
        start_datetime: startDatetime,
        end_datetime: endDatetime,
        reason: unavailabilityReason || undefined,
        is_all_day: unavailabilityIsAllDay,
      });
      
      setUnavailabilityDialogOpen(false);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create unavailability');
    } finally {
      setUnavailabilityCreating(false);
    }
  };

  const handleDeleteUnavailability = async (entryId: number) => {
    if (!confirm('Are you sure you want to delete this unavailability entry?')) return;
    
    try {
      await api.deleteEngineerUnavailability(entryId);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete unavailability');
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'cancelled':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'confirmed':
        return <Clock className="h-5 w-5 text-blue-500" />;
      default:
        return <AlertCircle className="h-5 w-5 text-yellow-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'cancelled':
        return 'bg-red-100 text-red-800';
      case 'confirmed':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-yellow-100 text-yellow-800';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  const formatTime = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Button variant="ghost" size="sm" onClick={() => navigate('/dashboard')}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
              <h1 className="text-2xl font-bold text-gray-900">Engineer Dashboard</h1>
            </div>
            <p className="text-gray-600">Welcome, {user?.full_name}</p>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-500">Total Bookings</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.total_bookings}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-500">Upcoming</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-blue-600">{stats.upcoming_bookings}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-500">Completed</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">{stats.completed_bookings}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-500">Pending</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-yellow-600">{stats.pending_bookings}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-500">Issues Reported</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-600">{stats.issues_reported}</div>
              </CardContent>
            </Card>
          </div>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-6">
            <TabsTrigger value="bookings">My Bookings</TabsTrigger>
            <TabsTrigger value="unavailability">My Unavailability</TabsTrigger>
            <TabsTrigger value="calendar">Calendar View</TabsTrigger>
          </TabsList>

          <TabsContent value="bookings">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Assigned Bookings</CardTitle>
                    <CardDescription>View and manage your assigned bookings</CardDescription>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="upcomingOnly"
                      checked={showUpcomingOnly}
                      onCheckedChange={(checked) => setShowUpcomingOnly(checked as boolean)}
                    />
                    <Label htmlFor="upcomingOnly">Show upcoming only</Label>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {bookings.length === 0 ? (
                  <p className="text-gray-500 text-center py-8">No bookings found</p>
                ) : (
                  <div className="space-y-4">
                    {bookings.map((booking) => (
                      <div
                        key={booking.id}
                        className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center space-x-3 mb-2">
                              {getStatusIcon(booking.status)}
                              <h3 className="font-semibold text-lg">{booking.order_reference}</h3>
                              <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(booking.status)}`}>
                                {booking.status.charAt(0).toUpperCase() + booking.status.slice(1)}
                              </span>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-gray-600">
                              <div>
                                <span className="font-medium">Customer:</span> {booking.customer_name}
                              </div>
                              <div className="flex items-center">
                                <Calendar className="h-4 w-4 mr-1" />
                                {formatDate(booking.scheduled_date)}
                              </div>
                              <div className="flex items-center">
                                <Clock className="h-4 w-4 mr-1" />
                                {formatTime(booking.scheduled_date)} ({booking.duration_hours}h)
                              </div>
                            </div>
                            {booking.product && (
                              <div className="mt-2 text-sm text-gray-600">
                                <span className="font-medium">Product:</span> {booking.product.name}
                                {booking.change_type && ` - ${booking.change_type.name}`}
                              </div>
                            )}
                            {booking.notes && (
                              <div className="mt-2 text-sm text-gray-500">
                                <span className="font-medium">Notes:</span> {booking.notes}
                              </div>
                            )}
                          </div>
                          <div className="ml-4">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => openStatusDialog(booking)}
                              disabled={booking.status === 'cancelled'}
                            >
                              Update Status
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="unavailability">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>My Unavailability</CardTitle>
                    <CardDescription>
                      Mark yourself as unavailable on specific dates/times. These entries override your Outlook calendar.
                    </CardDescription>
                  </div>
                  <Button onClick={openUnavailabilityDialog}>
                    <Plus className="h-4 w-4 mr-2" />
                    Add Unavailability
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {unavailability.length === 0 ? (
                  <p className="text-gray-500 text-center py-8">No unavailability entries</p>
                ) : (
                  <div className="space-y-4">
                    {unavailability.map((entry) => (
                      <div
                        key={entry.id}
                        className="border rounded-lg p-4 flex items-center justify-between"
                      >
                        <div>
                          <div className="flex items-center space-x-2 mb-1">
                            <XCircle className="h-5 w-5 text-red-500" />
                            <span className="font-medium">
                              {entry.is_all_day ? 'All Day' : `${formatTime(entry.start_datetime)} - ${formatTime(entry.end_datetime)}`}
                            </span>
                          </div>
                          <div className="text-sm text-gray-600">
                            {formatDate(entry.start_datetime)}
                            {entry.start_datetime.split('T')[0] !== entry.end_datetime.split('T')[0] && (
                              <> to {formatDate(entry.end_datetime)}</>
                            )}
                          </div>
                          {entry.reason && (
                            <div className="text-sm text-gray-500 mt-1">
                              <span className="font-medium">Reason:</span> {entry.reason}
                            </div>
                          )}
                          <div className="text-xs text-gray-400 mt-1">
                            Created: {formatDateTime(entry.created_at)}
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                          onClick={() => handleDeleteUnavailability(entry.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="calendar">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Calendar View</CardTitle>
                    <CardDescription>View your daily schedule at a glance</CardDescription>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const date = new Date(ganttDate);
                        date.setDate(date.getDate() - 1);
                        setGanttDate(date.toISOString().split('T')[0]);
                      }}
                    >
                      Previous Day
                    </Button>
                    <Input
                      type="date"
                      value={ganttDate}
                      onChange={(e) => setGanttDate(e.target.value)}
                      className="w-40"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const date = new Date(ganttDate);
                        date.setDate(date.getDate() + 1);
                        setGanttDate(date.toISOString().split('T')[0]);
                      }}
                    >
                      Next Day
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setGanttDate(new Date().toISOString().split('T')[0])}
                    >
                      Today
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="border rounded-lg overflow-hidden">
                  <div className="flex">
                    <div className="w-32 flex-shrink-0 bg-gray-50 border-r p-2 font-medium text-sm">
                      {formatDate(ganttDate)}
                    </div>
                    <div className="flex-1 overflow-x-auto">
                      <div className="flex min-w-[1200px]">
                        {Array.from({ length: 24 }, (_, i) => (
                          <div
                            key={i}
                            className="flex-1 text-center text-xs text-gray-500 border-r py-1"
                            style={{ minWidth: '50px' }}
                          >
                            {i.toString().padStart(2, '0')}:00
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="flex border-t">
                    <div className="w-32 flex-shrink-0 bg-gray-50 border-r p-2 text-sm text-gray-600">
                      My Schedule
                    </div>
                    <div className="flex-1 relative h-16 overflow-x-auto">
                      <div className="absolute inset-0 flex min-w-[1200px]">
                        {Array.from({ length: 24 }, (_, i) => (
                          <div
                            key={i}
                            className="flex-1 border-r border-gray-100"
                            style={{ minWidth: '50px' }}
                          />
                        ))}
                      </div>
                      {bookings
                        .filter((booking) => {
                          const bookingDate = new Date(booking.scheduled_date).toISOString().split('T')[0];
                          return bookingDate === ganttDate && booking.status !== 'cancelled';
                        })
                        .map((booking) => {
                          const startDate = new Date(booking.scheduled_date);
                          const startHour = startDate.getHours() + startDate.getMinutes() / 60;
                          const duration = booking.duration_hours;
                          const left = (startHour / 24) * 100;
                          const width = (duration / 24) * 100;
                          return (
                            <div
                              key={booking.id}
                              className="absolute top-1 h-14 bg-blue-500 text-white text-xs rounded px-1 overflow-hidden cursor-pointer hover:bg-blue-600 transition-colors"
                              style={{
                                left: `${left}%`,
                                width: `${width}%`,
                                minWidth: '60px',
                              }}
                              title={`${booking.order_reference} - ${booking.customer_name}`}
                              onClick={() => navigate(`/booking/${booking.id}`)}
                            >
                              <div className="font-medium truncate">{booking.order_reference}</div>
                              <div className="truncate opacity-80">{booking.customer_name}</div>
                              <div className="truncate opacity-80">
                                {formatTime(booking.scheduled_date)} ({booking.duration_hours}h)
                              </div>
                            </div>
                          );
                        })}
                      {unavailability
                        .filter((entry) => {
                          const startDate = new Date(entry.start_datetime).toISOString().split('T')[0];
                          const endDate = new Date(entry.end_datetime).toISOString().split('T')[0];
                          return startDate <= ganttDate && endDate >= ganttDate;
                        })
                        .map((entry) => {
                          const entryStartDate = new Date(entry.start_datetime);
                          const entryEndDate = new Date(entry.end_datetime);
                          
                          let startHour = 0;
                          let endHour = 24;
                          
                          if (entryStartDate.toISOString().split('T')[0] === ganttDate) {
                            startHour = entryStartDate.getHours() + entryStartDate.getMinutes() / 60;
                          }
                          if (entryEndDate.toISOString().split('T')[0] === ganttDate) {
                            endHour = entryEndDate.getHours() + entryEndDate.getMinutes() / 60;
                          }
                          
                          if (entry.is_all_day) {
                            startHour = 0;
                            endHour = 24;
                          }
                          
                          const duration = endHour - startHour;
                          const left = (startHour / 24) * 100;
                          const width = (duration / 24) * 100;
                          
                          return (
                            <div
                              key={`unavail-${entry.id}`}
                              className="absolute top-1 h-14 bg-red-200 text-red-800 text-xs rounded px-1 overflow-hidden border border-red-300"
                              style={{
                                left: `${left}%`,
                                width: `${width}%`,
                                minWidth: '40px',
                              }}
                              title={entry.reason || 'Unavailable'}
                            >
                              <div className="font-medium truncate">Unavailable</div>
                              <div className="truncate opacity-80">{entry.reason || 'No reason specified'}</div>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex items-center space-x-4 text-sm">
                  <div className="flex items-center">
                    <div className="w-4 h-4 bg-blue-500 rounded mr-2"></div>
                    <span>Bookings</span>
                  </div>
                  <div className="flex items-center">
                    <div className="w-4 h-4 bg-red-200 border border-red-300 rounded mr-2"></div>
                    <span>Unavailable</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>

      {/* Status Update Dialog */}
      <Dialog open={statusDialogOpen} onOpenChange={setStatusDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Update Booking Status</DialogTitle>
            <DialogDescription>
              Update the status for booking {selectedBooking?.order_reference}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>New Status</Label>
              <Select value={newStatus} onValueChange={setNewStatus}>
                <SelectTrigger>
                  <SelectValue placeholder="Select status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="confirmed">Confirmed</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="delayed">Delayed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Notes (optional)</Label>
              <Textarea
                value={statusNotes}
                onChange={(e) => setStatusNotes(e.target.value)}
                placeholder="Add any notes about this status update..."
                rows={3}
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="issueReported"
                checked={issueReported}
                onCheckedChange={(checked) => setIssueReported(checked as boolean)}
              />
              <Label htmlFor="issueReported" className="text-red-600">Report an issue</Label>
            </div>
            {issueReported && (
              <div className="space-y-2">
                <Label>Issue Description</Label>
                <Textarea
                  value={issueDescription}
                  onChange={(e) => setIssueDescription(e.target.value)}
                  placeholder="Describe the issue..."
                  rows={3}
                  className="border-red-200"
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setStatusDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleStatusUpdate} disabled={statusUpdating}>
              {statusUpdating ? 'Updating...' : 'Update Status'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Unavailability Dialog */}
      <Dialog open={unavailabilityDialogOpen} onOpenChange={setUnavailabilityDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Unavailability</DialogTitle>
            <DialogDescription>
              Mark yourself as unavailable for a specific date/time period
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="allDay"
                checked={unavailabilityIsAllDay}
                onCheckedChange={(checked) => setUnavailabilityIsAllDay(checked as boolean)}
              />
              <Label htmlFor="allDay">All day</Label>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Start Date</Label>
                <Input
                  type="date"
                  value={unavailabilityStartDate}
                  onChange={(e) => setUnavailabilityStartDate(e.target.value)}
                />
              </div>
              {!unavailabilityIsAllDay && (
                <div className="space-y-2">
                  <Label>Start Time</Label>
                  <Input
                    type="time"
                    value={unavailabilityStartTime}
                    onChange={(e) => setUnavailabilityStartTime(e.target.value)}
                  />
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>End Date</Label>
                <Input
                  type="date"
                  value={unavailabilityEndDate}
                  onChange={(e) => setUnavailabilityEndDate(e.target.value)}
                />
              </div>
              {!unavailabilityIsAllDay && (
                <div className="space-y-2">
                  <Label>End Time</Label>
                  <Input
                    type="time"
                    value={unavailabilityEndTime}
                    onChange={(e) => setUnavailabilityEndTime(e.target.value)}
                  />
                </div>
              )}
            </div>
            <div className="space-y-2">
              <Label>Reason (optional)</Label>
              <Textarea
                value={unavailabilityReason}
                onChange={(e) => setUnavailabilityReason(e.target.value)}
                placeholder="e.g., Annual leave, Training, Personal appointment..."
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUnavailabilityDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateUnavailability} disabled={unavailabilityCreating}>
              {unavailabilityCreating ? 'Creating...' : 'Add Unavailability'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
