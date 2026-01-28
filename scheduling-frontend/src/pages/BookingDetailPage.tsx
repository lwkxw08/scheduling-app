import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import { Booking } from '../types';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Calendar, ArrowLeft, Clock, User, AlertTriangle, Edit, Trash2, XCircle } from 'lucide-react';

export default function BookingDetailPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  
  const [booking, setBooking] = useState<Booking | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [isEditing, setIsEditing] = useState(false);
  const [editDate, setEditDate] = useState('');
  const [editTime, setEditTime] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [editAdditionalEmails, setEditAdditionalEmails] = useState('');
  
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  
  const isAdmin = user?.role === 'admin';

  useEffect(() => {
    loadBooking();
  }, [id]);

  const loadBooking = async () => {
    try {
      const data = await api.getBooking(parseInt(id!)) as Booking;
      setBooking(data);
      
      const date = new Date(data.scheduled_date);
      setEditDate(date.toISOString().split('T')[0]);
      setEditTime(date.toTimeString().slice(0, 5));
      setEditNotes(data.notes || '');
      setEditAdditionalEmails(data.additional_emails?.join(', ') || '');
    } catch (err: any) {
      setError(err.message || 'Failed to load booking');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveChanges = async () => {
    if (!booking) return;
    
    setIsSaving(true);
    setError('');
    
    try {
      const scheduledDate = `${editDate}T${editTime}:00`;
      const emailList = editAdditionalEmails
        .split(',')
        .map(e => e.trim())
        .filter(e => e.length > 0);
      
      await api.updateBooking(booking.id, {
        scheduled_date: scheduledDate,
        notes: editNotes,
        additional_emails: emailList.length > 0 ? emailList : [],
      });
      
      await loadBooking();
      setIsEditing(false);
    } catch (err: any) {
      setError(err.message || 'Failed to update booking');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelBooking = async () => {
    if (!booking) return;
    
    setIsCancelling(true);
    setError('');
    
    try {
      await api.cancelBooking(booking.id);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to cancel booking');
      setIsCancelling(false);
    }
  };

  const handlePermanentDelete = async () => {
    if (!booking) return;
    
    setIsDeleting(true);
    setError('');
    
    try {
      await api.permanentlyDeleteBooking(booking.id);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to delete booking');
      setIsDeleting(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'confirmed':
        return 'bg-green-100 text-green-800';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      case 'cancelled':
        return 'bg-red-100 text-red-800';
      case 'completed':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const canModify = booking && booking.status !== 'cancelled' && booking.status !== 'completed';

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-500">Loading booking...</p>
        </div>
      </div>
    );
  }

  if (!booking) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Booking Not Found</h2>
          <p className="text-gray-500 mb-4">{error || 'The booking you are looking for does not exist.'}</p>
          <Button onClick={() => navigate('/dashboard')}>Return to Dashboard</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center py-4">
            <Button variant="ghost" onClick={() => navigate('/dashboard')} className="mr-4">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
            <div className="flex-1">
              <h1 className="text-xl font-semibold text-gray-900">Booking Details</h1>
              <p className="text-sm text-gray-500">{booking.order_reference}</p>
            </div>
            <Badge className={getStatusColor(booking.status)}>{booking.status}</Badge>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Order Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label className="text-gray-500">Order Reference</Label>
                  <p className="font-medium">{booking.order_reference}</p>
                </div>
                <div>
                  <Label className="text-gray-500">Customer Name</Label>
                  <p className="font-medium">{booking.customer_name}</p>
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label className="text-gray-500">Product</Label>
                  <p className="font-medium">{booking.product?.name || 'N/A'}</p>
                </div>
                <div>
                  <Label className="text-gray-500">Change Type</Label>
                  <p className="font-medium">{booking.change_type?.name || 'N/A'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Schedule</CardTitle>
              {canModify && !isEditing && (
                <Button variant="outline" size="sm" onClick={() => setIsEditing(true)}>
                  <Edit className="w-4 h-4 mr-2" />
                  Edit
                </Button>
              )}
            </CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Date</Label>
                      <Input
                        type="date"
                        value={editDate}
                        onChange={(e) => setEditDate(e.target.value)}
                        min={new Date().toISOString().split('T')[0]}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Time</Label>
                      <Input
                        type="time"
                        value={editTime}
                        onChange={(e) => setEditTime(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Notes</Label>
                    <Textarea
                      value={editNotes}
                      onChange={(e) => setEditNotes(e.target.value)}
                      rows={3}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Additional Email Recipients</Label>
                    <Input
                      value={editAdditionalEmails}
                      onChange={(e) => setEditAdditionalEmails(e.target.value)}
                      placeholder="Enter email addresses separated by commas"
                    />
                    <p className="text-xs text-gray-500">
                      These email addresses will receive booking notifications
                    </p>
                  </div>
                  <div className="flex justify-end space-x-2">
                    <Button variant="outline" onClick={() => setIsEditing(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleSaveChanges} disabled={isSaving}>
                      {isSaving ? 'Saving...' : 'Save Changes'}
                    </Button>
                  </div>
                </>
              ) : (
                <>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="flex items-center">
                      <Calendar className="w-5 h-5 text-gray-400 mr-3" />
                      <div>
                        <Label className="text-gray-500">Date</Label>
                        <p className="font-medium">
                          {new Date(booking.scheduled_date).toLocaleDateString('en-GB', {
                            weekday: 'long',
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric',
                          })}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center">
                      <Clock className="w-5 h-5 text-gray-400 mr-3" />
                      <div>
                        <Label className="text-gray-500">Time</Label>
                        <p className="font-medium">
                          {new Date(booking.scheduled_date).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}{' '}
                          ({booking.duration_hours} hours)
                        </p>
                      </div>
                    </div>
                  </div>
                  {booking.notes && (
                    <div>
                      <Label className="text-gray-500">Notes</Label>
                      <p className="mt-1">{booking.notes}</p>
                    </div>
                  )}
                  {booking.additional_emails && booking.additional_emails.length > 0 && (
                    <div>
                      <Label className="text-gray-500">Additional Email Recipients</Label>
                      <p className="mt-1">{booking.additional_emails.join(', ')}</p>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Assigned Engineer</CardTitle>
            </CardHeader>
            <CardContent>
              {booking.engineer?.user ? (
                <div className="flex items-center">
                  <div className="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center mr-4">
                    <User className="w-6 h-6 text-indigo-600" />
                  </div>
                  <div>
                    <p className="font-medium">{booking.engineer.user.full_name}</p>
                    <p className="text-sm text-gray-500">{booking.engineer.calendar_email}</p>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500">No engineer assigned</p>
              )}
            </CardContent>
          </Card>

          {(booking.cancellation_fee > 0 || booking.expedite_fee > 0) && (
            <Card>
              <CardHeader>
                <CardTitle>Fees</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {booking.expedite_fee > 0 && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">Expedite Fee</span>
                      <span className="font-medium">£{booking.expedite_fee.toFixed(2)}</span>
                    </div>
                  )}
                  {booking.cancellation_fee > 0 && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">Late Change/Cancellation Fee</span>
                      <span className="font-medium">£{booking.cancellation_fee.toFixed(2)}</span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {canModify && (
            <Card className="border-red-200">
              <CardHeader>
                <CardTitle className="text-red-600">Danger Zone</CardTitle>
                <CardDescription>
                  Cancelling a booking may incur fees if done after the deadline
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Dialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
                  <DialogTrigger asChild>
                    <Button variant="destructive">
                      <Trash2 className="w-4 h-4 mr-2" />
                      Cancel Booking
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Cancel Booking</DialogTitle>
                      <DialogDescription>
                        Are you sure you want to cancel this booking? This action cannot be undone.
                        Late cancellations may incur additional fees.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="flex items-center p-4 bg-yellow-50 rounded-lg">
                      <AlertTriangle className="w-5 h-5 text-yellow-600 mr-3" />
                      <p className="text-sm text-yellow-800">
                        Please check the cancellation policy before proceeding.
                      </p>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowCancelDialog(false)}>
                        Keep Booking
                      </Button>
                      <Button
                        variant="destructive"
                        onClick={handleCancelBooking}
                        disabled={isCancelling}
                      >
                        {isCancelling ? 'Cancelling...' : 'Yes, Cancel Booking'}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </CardContent>
            </Card>
          )}

          {isAdmin && (
            <Card className="border-red-300 bg-red-50">
              <CardHeader>
                <CardTitle className="text-red-700">Admin: Permanent Delete</CardTitle>
                <CardDescription>
                  Permanently delete this booking record from the system. This cannot be undone.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
                  <DialogTrigger asChild>
                    <Button variant="destructive" className="bg-red-700 hover:bg-red-800">
                      <XCircle className="w-4 h-4 mr-2" />
                      Permanently Delete Booking
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Permanently Delete Booking</DialogTitle>
                      <DialogDescription>
                        This will permanently remove the booking and all associated records from the database.
                        This action cannot be undone.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="flex items-center p-4 bg-red-100 rounded-lg">
                      <AlertTriangle className="w-5 h-5 text-red-600 mr-3" />
                      <p className="text-sm text-red-800">
                        Warning: This will delete all booking data including fees, status history, and related records.
                      </p>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
                        Cancel
                      </Button>
                      <Button
                        variant="destructive"
                        className="bg-red-700 hover:bg-red-800"
                        onClick={handlePermanentDelete}
                        disabled={isDeleting}
                      >
                        {isDeleting ? 'Deleting...' : 'Yes, Permanently Delete'}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}
