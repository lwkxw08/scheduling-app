import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import { Booking, EngineerAvailability, AvailabilityResponse } from '../types';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Calendar, ArrowLeft, Clock, User, AlertTriangle, Edit, Trash2, XCircle, Loader2, AlertCircle, UserCog, Paperclip, Upload, Download, X } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

// Status Change Section Component
function StatusChangeSection({ booking, isAdmin, onStatusChanged }: {
  booking: Booking; 
  isAdmin: boolean; 
  onStatusChanged: () => void;
}) {
  const [selectedStatus, setSelectedStatus] = useState<string>(booking.status);
  const [statusNotes, setStatusNotes] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState('');

  const statusOptions: string[] = isAdmin 
    ? ['pending', 'confirmed', 'completed', 'delayed', 'rejected']
    : ['delayed', 'rejected'];

  const handleStatusChange = async () => {
    if (selectedStatus === booking.status && !statusNotes) return;
    
    setIsUpdating(true);
    setError('');
    
    try {
      await api.adminUpdateBookingStatus(booking.id, selectedStatus, statusNotes || undefined);
      setStatusNotes('');
      onStatusChanged();
    } catch (err: any) {
      setError(err.message || 'Failed to update status');
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}
      
      <div className="space-y-2">
        <Label>Current Status</Label>
        <Badge className={
          booking.status === 'confirmed' ? 'bg-green-100 text-green-800' :
          booking.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
          booking.status === 'completed' ? 'bg-blue-100 text-blue-800' :
          booking.status === 'delayed' ? 'bg-orange-100 text-orange-800' :
          booking.status === 'rejected' ? 'bg-purple-100 text-purple-800' :
          'bg-gray-100 text-gray-800'
        }>
          {booking.status}
        </Badge>
      </div>

      <div className="space-y-2">
        <Label>Change Status To</Label>
        <Select value={selectedStatus} onValueChange={setSelectedStatus}>
          <SelectTrigger>
            <SelectValue placeholder="Select status" />
          </SelectTrigger>
          <SelectContent>
            {statusOptions.map((status) => (
              <SelectItem key={status} value={status}>
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Notes (optional)</Label>
        <Textarea
          placeholder={selectedStatus === 'delayed' ? 'Describe the issue or reason for delay...' : 'Add any notes about this status change...'}
          value={statusNotes}
          onChange={(e) => setStatusNotes(e.target.value)}
          rows={3}
        />
        <p className="text-xs text-gray-500">Notes will be timestamped and attributed to you</p>
      </div>

      <Button 
        onClick={handleStatusChange} 
        disabled={isUpdating || (selectedStatus === booking.status && !statusNotes)}
        className={selectedStatus === 'delayed' ? 'bg-orange-600 hover:bg-orange-700' : ''}
      >
        {isUpdating ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            Updating...
          </>
        ) : (
          `Update Status${selectedStatus !== booking.status ? ` to ${selectedStatus.charAt(0).toUpperCase() + selectedStatus.slice(1)}` : ''}`
        )}
      </Button>
    </div>
  );
}

export default function BookingDetailPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  
  const [booking, setBooking] = useState<Booking | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  
  
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  
  // Amendment workflow state
  const [showAmendmentDialog, setShowAmendmentDialog] = useState(false);
  const [amendmentStep, setAmendmentStep] = useState(1);
  const [amendmentDate, setAmendmentDate] = useState('');
  const [amendmentDuration, setAmendmentDuration] = useState<number>(1);
  const [availability, setAvailability] = useState<EngineerAvailability[]>([]);
  const [selectedEngineerId, setSelectedEngineerId] = useState<number | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [isCheckingAvailability, setIsCheckingAvailability] = useState(false);
  const [showNoAvailabilityOptions, setShowNoAvailabilityOptions] = useState(false);
  const [showExpediteDialog, setShowExpediteDialog] = useState(false);
  const [expediteFeeAcknowledged, setExpediteFeeAcknowledged] = useState(false);
  const [isSubmittingExpedite, setIsSubmittingExpedite] = useState(false);
  const [expediteRequestedTime, setExpediteRequestedTime] = useState('09:00');
  const [applicableFees, setApplicableFees] = useState<Array<{
    fee_id: number | null;
    name: string;
    fee_type: string;
    amount: number;
    requires_approval: boolean;
    is_per_hour: boolean;
  }>>([]);
  const [feesTotal, setFeesTotal] = useState<number>(0);
  const [isLoadingFees, setIsLoadingFees] = useState(false);
    const [amendmentNotes, setAmendmentNotes] = useState('');
  
    // Reassign engineer state (admin only)
    const [showReassignDialog, setShowReassignDialog] = useState(false);
    const [allEngineers, setAllEngineers] = useState<any[]>([]);
    const [selectedReassignEngineerId, setSelectedReassignEngineerId] = useState<string>('');
    const [isReassigning, setIsReassigning] = useState(false);
    const [isLoadingEngineers, setIsLoadingEngineers] = useState(false);
  
    // Attachments state (admin only)
    const [attachments, setAttachments] = useState<any[]>([]);
    const [isLoadingAttachments, setIsLoadingAttachments] = useState(false);
    const [isUploadingAttachment, setIsUploadingAttachment] = useState(false);
    const [isDeletingAttachment, setIsDeletingAttachment] = useState<number | null>(null);
  
    const isAdmin = user?.role === 'admin';

  useEffect(() => {
    loadBooking();
  }, [id]);

  useEffect(() => {
    if (booking && isAdmin) {
      loadAttachments();
    }
  }, [booking?.id, isAdmin]);

  const loadBooking = async () => {
    try {
      const data = await api.getBooking(parseInt(id!)) as Booking;
      setBooking(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load booking');
    } finally {
      setIsLoading(false);
    }
  };

  const loadAttachments = async () => {
    if (!booking) return;
    setIsLoadingAttachments(true);
    try {
      const data = await api.getBookingAttachments(booking.id);
      setAttachments(data as any[]);
    } catch (err: any) {
      console.error('Failed to load attachments:', err);
    } finally {
      setIsLoadingAttachments(false);
    }
  };

  const handleUploadAttachment = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!booking || !e.target.files || e.target.files.length === 0) return;
    
    const file = e.target.files[0];
    setIsUploadingAttachment(true);
    
    try {
      await api.addBookingAttachment(booking.id, file);
      await loadAttachments();
    } catch (err: any) {
      setError(err.message || 'Failed to upload attachment');
    } finally {
      setIsUploadingAttachment(false);
      e.target.value = '';
    }
  };

  const handleDeleteAttachment = async (attachmentId: number) => {
    if (!booking) return;
    
    setIsDeletingAttachment(attachmentId);
    try {
      await api.deleteBookingAttachment(booking.id, attachmentId);
      await loadAttachments();
    } catch (err: any) {
      setError(err.message || 'Failed to delete attachment');
    } finally {
      setIsDeletingAttachment(null);
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

    const loadEngineersForReassign = async () => {
      setIsLoadingEngineers(true);
      try {
        const engineers = await api.getEngineers();
        setAllEngineers(engineers as any[]);
        if (booking?.engineer?.id) {
          setSelectedReassignEngineerId(booking.engineer.id.toString());
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load engineers');
      } finally {
        setIsLoadingEngineers(false);
      }
    };

    const handleReassignEngineer = async () => {
      if (!booking || !selectedReassignEngineerId) return;
    
      setIsReassigning(true);
      setError('');
    
      try {
        await api.updateBooking(booking.id, {
          engineer_id: parseInt(selectedReassignEngineerId)
        });
        await loadBooking();
        setShowReassignDialog(false);
      } catch (err: any) {
        setError(err.message || 'Failed to reassign engineer');
      } finally {
        setIsReassigning(false);
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
      case 'delayed':
        return 'bg-orange-100 text-orange-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const openAmendmentDialog = () => {
    if (booking) {
      setAmendmentDate('');
      setAmendmentDuration(booking.duration_hours);
      setAmendmentStep(1);
      setAvailability([]);
      setSelectedEngineerId(null);
      setSelectedSlot(null);
      setShowNoAvailabilityOptions(false);
      setAmendmentNotes(booking.notes || '');
      setShowAmendmentDialog(true);
    }
  };

  const handleCheckAmendmentAvailability = async () => {
    if (!booking || !amendmentDate) {
      setError('Please select a date');
      return;
    }

    setIsCheckingAvailability(true);
    setError('');
    setShowNoAvailabilityOptions(false);

    try {
      const response = await api.checkAvailability(
        amendmentDate, 
        booking.product_id, 
        booking.change_type_id, 
        amendmentDuration
      ) as AvailabilityResponse;
      
      setAvailability(response.engineers);
      
      // Check if any engineer has available slots
      const hasAvailableSlots = response.engineers.some(eng => 
        eng.slots.some(slot => slot.is_available)
      );
      
      if (response.engineers.length === 0 || !hasAvailableSlots) {
        setError('No engineers available for the selected date');
        setShowNoAvailabilityOptions(true);
      } else {
        setAmendmentStep(2);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to check availability');
    } finally {
      setIsCheckingAvailability(false);
    }
  };

  const handleSubmitAmendment = async () => {
    if (!booking || !selectedEngineerId || !selectedSlot) {
      setError('Please select an engineer and time slot');
      return;
    }

    setIsSaving(true);
    setError('');

    try {
      const scheduledDate = `${amendmentDate}T${selectedSlot}:00`;
      
      await api.updateBooking(booking.id, {
        scheduled_date: scheduledDate,
        engineer_id: selectedEngineerId,
        duration_hours: amendmentDuration,
        notes: amendmentNotes,
      });
      
      setShowAmendmentDialog(false);
      await loadBooking();
    } catch (err: any) {
      setError(err.message || 'Failed to update booking');
    } finally {
      setIsSaving(false);
    }
  };

  const loadApplicableFees = async (requestedTime: string) => {
    if (!booking || !amendmentDate) return;
    
    setIsLoadingFees(true);
    try {
      const requestedDateTime = `${amendmentDate}T${requestedTime}:00`;
      
      const result = await api.previewApplicableFees({
        product_id: booking.product_id,
        change_type_id: booking.change_type_id,
        scheduled_date: requestedDateTime,
        duration_hours: amendmentDuration || 1,
      });
      
      setApplicableFees(result.fees);
      setFeesTotal(result.total);
    } catch (err) {
      console.error('Failed to load applicable fees:', err);
      setApplicableFees([]);
      setFeesTotal(0);
    } finally {
      setIsLoadingFees(false);
    }
  };

  const handleOpenExpediteDialog = async () => {
    setExpediteRequestedTime('09:00');
    setExpediteFeeAcknowledged(false);
    setShowExpediteDialog(true);
    await loadApplicableFees('09:00');
  };

  const handleSubmitAmendmentExpedite = async () => {
    if (!booking || !expediteFeeAcknowledged) {
      setError('Please acknowledge the fee total before submitting');
      return;
    }

    setIsSubmittingExpedite(true);
    setError('');

    try {
      const requestedDateTime = `${amendmentDate}T${expediteRequestedTime}:00`;

      await api.createExpediteRequest({
        product_id: booking.product_id,
        change_type_id: booking.change_type_id,
        order_reference: booking.order_reference,
        customer_name: booking.customer_name,
        requested_date: requestedDateTime,
        duration_hours: amendmentDuration,
        notes: `Amendment request for booking #${booking.id}. ${amendmentNotes}`,
        fee_acknowledged: true,
      });

      setShowExpediteDialog(false);
      setShowAmendmentDialog(false);
      navigate('/dashboard', { state: { message: 'Amendment expedite request submitted successfully. You will be notified once it is reviewed.' } });
    } catch (err: any) {
      setError(err.message || 'Failed to submit expedite request');
    } finally {
      setIsSubmittingExpedite(false);
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
              {canModify && (
                <Button variant="outline" size="sm" onClick={openAmendmentDialog}>
                  <Edit className="w-4 h-4 mr-2" />
                  Request Amendment
                </Button>
              )}
            </CardHeader>
            <CardContent className="space-y-4">
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
              {booking.additional_emails && booking.additional_emails.length > 0 && (
                <div>
                  <Label className="text-gray-500">Additional Email Recipients</Label>
                  <p className="mt-1">{booking.additional_emails.join(', ')}</p>
                </div>
              )}
            </CardContent>
          </Card>

                    <Card>
                      <CardHeader className="flex flex-row items-center justify-between">
                        <CardTitle>Assigned Engineer</CardTitle>
                        {isAdmin && booking.status !== 'cancelled' && booking.status !== 'completed' && (
                          <Dialog open={showReassignDialog} onOpenChange={(open) => {
                            setShowReassignDialog(open);
                            if (open) loadEngineersForReassign();
                          }}>
                            <DialogTrigger asChild>
                              <Button variant="outline" size="sm">
                                <UserCog className="w-4 h-4 mr-2" />
                                Reassign
                              </Button>
                            </DialogTrigger>
                            <DialogContent>
                              <DialogHeader>
                                <DialogTitle>Reassign Engineer</DialogTitle>
                                <DialogDescription>
                                  Select a different engineer to assign to this booking.
                                </DialogDescription>
                              </DialogHeader>
                              <div className="space-y-4 py-4">
                                {isLoadingEngineers ? (
                                  <div className="flex justify-center py-4">
                                    <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                                  </div>
                                ) : (
                                  <div className="space-y-2">
                                    <Label>Select Engineer</Label>
                                    <Select value={selectedReassignEngineerId} onValueChange={setSelectedReassignEngineerId}>
                                      <SelectTrigger>
                                        <SelectValue placeholder="Select an engineer" />
                                      </SelectTrigger>
                                      <SelectContent>
                                        {allEngineers.map((eng) => (
                                          <SelectItem key={eng.id} value={eng.id.toString()}>
                                            {eng.user?.full_name || eng.calendar_email}
                                          </SelectItem>
                                        ))}
                                      </SelectContent>
                                    </Select>
                                  </div>
                                )}
                              </div>
                              <DialogFooter>
                                <Button variant="outline" onClick={() => setShowReassignDialog(false)}>
                                  Cancel
                                </Button>
                                <Button 
                                  onClick={handleReassignEngineer} 
                                  disabled={isReassigning || !selectedReassignEngineerId}
                                >
                                  {isReassigning ? (
                                    <>
                                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                      Reassigning...
                                    </>
                                  ) : (
                                    'Reassign Engineer'
                                  )}
                                </Button>
                              </DialogFooter>
                            </DialogContent>
                          </Dialog>
                        )}
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

          {/* Status Management Section - Admin/Engineer */}
          {(isAdmin || (user?.role === 'engineer' && booking.engineer?.user_id === user?.id)) && booking.status !== 'cancelled' && (
            <Card>
              <CardHeader>
                <CardTitle>Status Management</CardTitle>
                <CardDescription>
                  {isAdmin ? 'Update the booking status' : 'Mark this booking as delayed if there are issues'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <StatusChangeSection 
                  booking={booking} 
                  isAdmin={isAdmin} 
                  onStatusChanged={loadBooking}
                />
              </CardContent>
            </Card>
          )}

          {/* Additional Information Section */}
          <Card>
            <CardHeader>
              <CardTitle>Additional Information</CardTitle>
              <CardDescription>
                Additional details and information about this booking
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <Label className="text-gray-500">Custom Fields</Label>
                  {booking.custom_fields_data && Object.keys(booking.custom_fields_data).length > 0 ? (
                    <div className="mt-2 space-y-2">
                      {Object.entries(booking.custom_fields_data).map(([key, value]) => (
                        <div key={key} className="flex justify-between text-sm">
                          <span className="text-gray-600">{key}:</span>
                          <span className="font-medium">{String(value)}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-1 text-gray-400 text-sm">No additional information provided</p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Booking Notes Section */}
          <Card>
            <CardHeader>
              <CardTitle>Booking Notes</CardTitle>
              <CardDescription>
                Notes and comments about this booking
              </CardDescription>
            </CardHeader>
            <CardContent>
              {booking.notes ? (
                <p className="text-gray-700 whitespace-pre-wrap">{booking.notes}</p>
              ) : (
                <p className="text-gray-400 text-sm">No booking notes</p>
              )}
            </CardContent>
          </Card>

          {/* Engineer Notes Section */}
          <Card>
            <CardHeader>
              <CardTitle>Engineer Notes</CardTitle>
              <CardDescription>
                Notes from the assigned engineer
              </CardDescription>
            </CardHeader>
            <CardContent>
              {booking.engineer_notes ? (
                <p className="text-gray-700 whitespace-pre-wrap">{booking.engineer_notes}</p>
              ) : (
                <p className="text-gray-400 text-sm">No engineer notes</p>
              )}
            </CardContent>
          </Card>

          {/* Engineer Issue Description Section */}
          <Card className={booking.issue_description && !booking.issue_resolved ? 'border-amber-300 bg-amber-50' : ''}>
            <CardHeader>
              <CardTitle className={booking.issue_description && !booking.issue_resolved ? 'text-amber-700' : ''}>
                Engineer Issue Report
              </CardTitle>
              <CardDescription>
                Issues reported by the engineer regarding this booking
              </CardDescription>
            </CardHeader>
            <CardContent>
              {booking.issue_description ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Badge variant={booking.issue_resolved ? 'secondary' : 'destructive'}>
                      {booking.issue_resolved ? 'Resolved' : 'Open'}
                    </Badge>
                    {booking.issue_reported_at && (
                      <span className="text-sm text-gray-500">
                        Reported: {new Date(booking.issue_reported_at).toLocaleString()}
                      </span>
                    )}
                  </div>
                  <p className="text-gray-700 whitespace-pre-wrap">{booking.issue_description}</p>
                </div>
              ) : (
                <p className="text-gray-400 text-sm">No issues reported</p>
              )}
            </CardContent>
          </Card>

          {/* Fees Section */}
          <Card>
            <CardHeader>
              <CardTitle>Fees</CardTitle>
              <CardDescription>
                Fees associated with this booking
              </CardDescription>
            </CardHeader>
            <CardContent>
              {(booking.fees && booking.fees.length > 0) || booking.expedite_fee > 0 || booking.cancellation_fee > 0 ? (
                <div className="space-y-4">
                  {/* New Fee System - BookingFee records */}
                  {booking.fees && booking.fees.length > 0 && (
                    <div className="space-y-2">
                      <Label className="text-gray-500 text-sm">Applied Fees</Label>
                      <div className="border rounded-lg divide-y">
                        {booking.fees.map((fee) => (
                          <div key={fee.id} className="flex items-center justify-between p-3">
                            <div>
                              <p className="font-medium">{fee.fee_name || 'Fee'}</p>
                              <p className="text-sm text-gray-500">{fee.fee_type}</p>
                            </div>
                            <div className="text-right">
                              <p className="font-medium">£{fee.amount.toFixed(2)}</p>
                              <Badge 
                                variant={fee.status === 'approved' ? 'default' : fee.status === 'pending' ? 'secondary' : 'outline'}
                                className={
                                  fee.status === 'approved' ? 'bg-green-100 text-green-800' :
                                  fee.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                                  'bg-gray-100 text-gray-800'
                                }
                              >
                                {fee.status}
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </div>
                      {/* Fee Totals */}
                      <div className="mt-3 pt-3 border-t space-y-1">
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-600">Total Approved</span>
                          <span className="font-medium text-green-600">
                            £{booking.fees.filter(f => f.status === 'approved').reduce((sum, f) => sum + f.amount, 0).toFixed(2)}
                          </span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-600">Total Pending</span>
                          <span className="font-medium text-yellow-600">
                            £{booking.fees.filter(f => f.status === 'pending').reduce((sum, f) => sum + f.amount, 0).toFixed(2)}
                          </span>
                        </div>
                        {booking.fees.some(f => f.status === 'waived') && (
                          <div className="flex justify-between text-sm">
                            <span className="text-gray-600">Total Waived</span>
                            <span className="font-medium text-gray-500">
                              £{booking.fees.filter(f => f.status === 'waived').reduce((sum, f) => sum + f.amount, 0).toFixed(2)}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  
                  {/* Legacy Fees (expedite_fee, cancellation_fee on Booking table) */}
                  {(booking.expedite_fee > 0 || booking.cancellation_fee > 0) && (
                    <div className="space-y-2">
                      <Label className="text-gray-500 text-sm">Legacy Fees</Label>
                      <div className="space-y-2">
                        {booking.expedite_fee > 0 && (
                          <div className="flex justify-between p-2 bg-gray-50 rounded">
                            <span className="text-gray-600">Expedite Fee</span>
                            <span className="font-medium">£{booking.expedite_fee.toFixed(2)}</span>
                          </div>
                        )}
                        {booking.cancellation_fee > 0 && (
                          <div className="flex justify-between p-2 bg-gray-50 rounded">
                            <span className="text-gray-600">Late Change/Cancellation Fee</span>
                            <span className="font-medium">£{booking.cancellation_fee.toFixed(2)}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-gray-400 text-sm">No fees associated with this booking</p>
              )}
            </CardContent>
          </Card>

          {isAdmin && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Attachments</CardTitle>
                  <CardDescription>
                    Files attached to this booking
                  </CardDescription>
                </div>
                <div>
                  <input
                    type="file"
                    id="attachment-upload"
                    className="hidden"
                    onChange={handleUploadAttachment}
                    disabled={isUploadingAttachment}
                  />
                  <label htmlFor="attachment-upload">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={isUploadingAttachment}
                      asChild
                    >
                      <span>
                        {isUploadingAttachment ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Uploading...
                          </>
                        ) : (
                          <>
                            <Upload className="w-4 h-4 mr-2" />
                            Upload File
                          </>
                        )}
                      </span>
                    </Button>
                  </label>
                </div>
              </CardHeader>
              <CardContent>
                {isLoadingAttachments ? (
                  <div className="flex justify-center py-4">
                    <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                  </div>
                ) : attachments.length > 0 ? (
                  <div className="space-y-2">
                    {attachments.map((attachment) => (
                      <div
                        key={attachment.id}
                        className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                      >
                        <div className="flex items-center">
                          <Paperclip className="w-4 h-4 text-gray-400 mr-3" />
                          <div>
                            <p className="font-medium text-sm">{attachment.original_filename}</p>
                            <p className="text-xs text-gray-500">
                              Uploaded {new Date(attachment.uploaded_at).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <a
                            href={api.getBookingAttachmentUrl(attachment.stored_filename)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-indigo-600 hover:text-indigo-800"
                          >
                            <Download className="w-4 h-4" />
                          </a>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteAttachment(attachment.id)}
                            disabled={isDeletingAttachment === attachment.id}
                            className="text-red-600 hover:text-red-800 hover:bg-red-50"
                          >
                            {isDeletingAttachment === attachment.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <X className="w-4 h-4" />
                            )}
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-400 text-sm">No attachments</p>
                )}
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

      {/* Amendment Dialog */}
      <Dialog open={showAmendmentDialog} onOpenChange={setShowAmendmentDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Request Amendment</DialogTitle>
            <DialogDescription>
              {amendmentStep === 1 
                ? 'Select a new date and duration for your booking'
                : 'Select an available time slot'
              }
            </DialogDescription>
          </DialogHeader>

          {error && (
            <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
                <div className="flex-1">
                  <p>{error}</p>
                  {showNoAvailabilityOptions && (
                    <div className="mt-4 p-4 bg-white rounded-lg border border-gray-200">
                      <h4 className="font-medium text-gray-900 mb-2">No availability found</h4>
                      <p className="text-sm text-gray-600 mb-4">
                        Would you like to submit a special resourcing request for this date and time? Additional fees may apply
                      </p>
                      <Button
                        onClick={handleOpenExpediteDialog}
                        className="bg-amber-600 hover:bg-amber-700"
                      >
                        Submit Request
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {amendmentStep === 1 && (
            <div className="space-y-4">
              <div className="p-4 bg-gray-50 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-2">Current Booking</h4>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-gray-500">Date:</span>{' '}
                    <span className="font-medium">
                      {booking && new Date(booking.scheduled_date).toLocaleDateString('en-GB')}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Time:</span>{' '}
                    <span className="font-medium">
                      {booking && new Date(booking.scheduled_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Engineer:</span>{' '}
                    <span className="font-medium">{booking?.engineer?.user?.full_name || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Duration:</span>{' '}
                    <span className="font-medium">{booking?.duration_hours} hours</span>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label>New Date *</Label>
                <Input
                  type="date"
                  value={amendmentDate}
                  onChange={(e) => setAmendmentDate(e.target.value)}
                  min={new Date().toISOString().split('T')[0]}
                />
              </div>

              <div className="space-y-2">
                <Label>Duration (hours)</Label>
                <Input
                  type="number"
                  min="0.5"
                  step="0.5"
                  value={amendmentDuration}
                  onChange={(e) => setAmendmentDuration(parseFloat(e.target.value))}
                />
              </div>

              <div className="space-y-2">
                <Label>Notes</Label>
                <Textarea
                  value={amendmentNotes}
                  onChange={(e) => setAmendmentNotes(e.target.value)}
                  rows={3}
                  placeholder="Add any notes for this amendment..."
                />
              </div>
            </div>
          )}

          {amendmentStep === 2 && (
            <div className="space-y-4">
              <div className="p-4 bg-blue-50 rounded-lg">
                <p className="text-sm text-blue-800">
                  <strong>Selected Date:</strong> {new Date(amendmentDate).toLocaleDateString('en-GB', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                </p>
              </div>

              {availability.length === 0 ? (
                <div className="text-center py-8">
                  <Calendar className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-500">No available slots found</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {availability.map((engineer) => (
                    <div key={engineer.engineer_id} className="border rounded-lg p-4">
                      <div className="flex items-center mb-4">
                        <div className="w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center mr-3">
                          <User className="w-5 h-5 text-indigo-600" />
                        </div>
                        <div>
                          <h4 className="font-medium text-gray-900">{engineer.engineer_name}</h4>
                          <p className="text-sm text-gray-500">{engineer.calendar_email}</p>
                        </div>
                      </div>
                      <div className="grid grid-cols-4 gap-2">
                        {engineer.slots.map((slot) => (
                          <Button
                            key={slot.start_time}
                            variant={
                              selectedEngineerId === engineer.engineer_id && selectedSlot === slot.start_time
                                ? 'default'
                                : 'outline'
                            }
                            disabled={!slot.is_available}
                            onClick={() => {
                              setSelectedEngineerId(engineer.engineer_id);
                              setSelectedSlot(slot.start_time);
                              setError('');
                            }}
                            className="text-sm"
                          >
                            <Clock className="w-3 h-3 mr-1" />
                            {slot.start_time}
                          </Button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            {amendmentStep === 1 ? (
              <>
                <Button variant="outline" onClick={() => setShowAmendmentDialog(false)}>
                  Cancel
                </Button>
                <Button 
                  onClick={handleCheckAmendmentAvailability} 
                  disabled={!amendmentDate || isCheckingAvailability}
                >
                  {isCheckingAvailability ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Checking...
                    </>
                  ) : (
                    'Check Availability'
                  )}
                </Button>
              </>
            ) : (
              <>
                <Button variant="outline" onClick={() => { setAmendmentStep(1); setError(''); }}>
                  Back
                </Button>
                <Button 
                  onClick={handleSubmitAmendment} 
                  disabled={!selectedEngineerId || !selectedSlot || isSaving}
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    'Confirm Amendment'
                  )}
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Expedite Request Dialog for Amendment */}
      <Dialog open={showExpediteDialog} onOpenChange={setShowExpediteDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Submit Special Resourcing Request</DialogTitle>
            <DialogDescription>
              Request special resourcing for {amendmentDate}. Your request will be reviewed by an administrator.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-lg space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Order Reference:</span>
                <span className="font-medium">{booking?.order_reference}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Customer:</span>
                <span className="font-medium">{booking?.customer_name}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Date:</span>
                <span className="font-medium">{amendmentDate}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Duration:</span>
                <span className="font-medium">{amendmentDuration} hours</span>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Preferred Time</Label>
              <Input
                type="time"
                value={expediteRequestedTime}
                onChange={(e) => {
                  setExpediteRequestedTime(e.target.value);
                  loadApplicableFees(e.target.value);
                }}
              />
              <p className="text-xs text-gray-500">Select your preferred start time for this booking</p>
            </div>

            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
              <h4 className="font-medium text-amber-800 mb-3">Applicable Fees</h4>
              {isLoadingFees ? (
                <div className="flex items-center gap-2 text-amber-700">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Loading fees...</span>
                </div>
              ) : applicableFees.length > 0 ? (
                <div className="space-y-2">
                  {applicableFees.map((fee, index) => (
                    <div key={index} className="flex justify-between items-center text-sm">
                      <span className="text-amber-700">
                        {fee.name}
                        {fee.requires_approval && (
                          <span className="ml-2 text-xs bg-amber-200 text-amber-800 px-2 py-0.5 rounded">
                            Requires Approval
                          </span>
                        )}
                      </span>
                      <span className="font-medium text-amber-800">£{fee.amount.toFixed(2)}</span>
                    </div>
                  ))}
                  <div className="border-t border-amber-300 pt-2 mt-2 flex justify-between items-center">
                    <span className="font-medium text-amber-800">Total</span>
                    <span className="font-bold text-amber-900">£{feesTotal.toFixed(2)}</span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-amber-700">No additional fees apply to this request.</p>
              )}
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="feeAcknowledged"
                checked={expediteFeeAcknowledged}
                onCheckedChange={(checked) => setExpediteFeeAcknowledged(checked as boolean)}
              />
              <Label htmlFor="feeAcknowledged" className="text-sm">
                {feesTotal > 0 
                  ? `I acknowledge and accept the fee total of £${feesTotal.toFixed(2)}`
                  : 'I understand this is a special resourcing request and will be reviewed by an administrator'
                }
              </Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowExpediteDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmitAmendmentExpedite}
              disabled={!expediteFeeAcknowledged || isSubmittingExpedite}
              className="bg-amber-600 hover:bg-amber-700"
            >
              {isSubmittingExpedite ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Submitting...
                </>
              ) : (
                'Submit Request'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
