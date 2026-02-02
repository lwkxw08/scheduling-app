import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import { Product, ChangeType, CustomField, EngineerAvailability, AvailabilityResponse } from '../types';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Checkbox } from '../components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Calendar, ArrowLeft, Clock, User, Check, Paperclip, Upload, Loader2, AlertCircle } from 'lucide-react';

export default function BookingPage() {
  const navigate = useNavigate();
  useAuth();
  
  const [step, setStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const [products, setProducts] = useState<Product[]>([]);
  const [changeTypes, setChangeTypes] = useState<ChangeType[]>([]);
  const [customFields, setCustomFields] = useState<CustomField[]>([]);

  const [orderReference, setOrderReference] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [productId, setProductId] = useState<number | null>(null);
  const [changeTypeId, setChangeTypeId] = useState<number | null>(null);
  const [customFieldValues, setCustomFieldValues] = useState<Record<string, any>>({});
  const [notes, setNotes] = useState('');
  const [additionalEmails, setAdditionalEmails] = useState('');

  const [selectedDate, setSelectedDate] = useState('');
  const [durationHours, setDurationHours] = useState<number>(1);
  const [customDuration, setCustomDuration] = useState('');

  const [availability, setAvailability] = useState<EngineerAvailability[]>([]);
  const [selectedEngineerId, setSelectedEngineerId] = useState<number | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);

  const [isExpedited, setIsExpedited] = useState(false);

  const [engineerAttachmentUrl, setEngineerAttachmentUrl] = useState('');
  const [customerAttachmentUrl, setCustomerAttachmentUrl] = useState('');
  const [isUploadingEngineerAttachment, setIsUploadingEngineerAttachment] = useState(false);
  const [isUploadingCustomerAttachment, setIsUploadingCustomerAttachment] = useState(false);

  // Expedite request state
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

  useEffect(() => {
    loadFormData();
  }, []);

  const loadFormData = async () => {
    try {
      const [productsData, changeTypesData, customFieldsData] = await Promise.all([
        api.getProducts(),
        api.getChangeTypes(),
        api.getCustomFields(),
      ]);
      setProducts(productsData as Product[]);
      setChangeTypes(changeTypesData as ChangeType[]);
      setCustomFields(customFieldsData as CustomField[]);
    } catch (error) {
      console.error('Failed to load form data:', error);
    }
  };

  const handleCheckAvailability = async () => {
    if (!productId || !changeTypeId || !selectedDate) {
      setError('Please fill in all required fields');
      return;
    }

    setIsLoading(true);
    setError('');
    setShowNoAvailabilityOptions(false);

    try {
      const duration = durationHours === 0 ? parseFloat(customDuration) : durationHours;
      const response = await api.checkAvailability(selectedDate, productId, changeTypeId, duration) as AvailabilityResponse;
      setAvailability(response.engineers);
      
      // Check if any engineer has available slots
      const hasAvailableSlots = response.engineers.some(eng => 
        eng.slots.some(slot => slot.is_available)
      );
      
      if (response.engineers.length === 0 || !hasAvailableSlots) {
        setError('No engineers available for the selected criteria');
        setShowNoAvailabilityOptions(true);
      } else {
        setStep(3);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to check availability');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmitBooking = async () => {
    if (!selectedEngineerId || !selectedSlot) {
      setError('Please select an engineer and time slot');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const duration = durationHours === 0 ? parseFloat(customDuration) : durationHours;
      const scheduledDate = `${selectedDate}T${selectedSlot}:00`;

      const emailList = additionalEmails
        .split(',')
        .map(e => e.trim())
        .filter(e => e.length > 0);

      await api.createBooking({
        order_reference: orderReference,
        customer_name: customerName,
        engineer_id: selectedEngineerId,
        product_id: productId!,
        change_type_id: changeTypeId!,
        scheduled_date: scheduledDate,
        duration_hours: duration,
        custom_fields_data: customFieldValues,
        notes: notes || undefined,
        additional_emails: emailList.length > 0 ? emailList : undefined,
        engineer_attachment_url: engineerAttachmentUrl || undefined,
        customer_attachment_url: customerAttachmentUrl || undefined,
        is_expedited: isExpedited,
      });

      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to create booking');
    } finally {
      setIsLoading(false);
    }
  };

  const handleEngineerAttachmentUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploadingEngineerAttachment(true);
    try {
      const result = await api.uploadFile(file, 'attachment');
      const fullUrl = api.getFileUrl(result.url);
      setEngineerAttachmentUrl(fullUrl);
    } catch (error) {
      console.error('Failed to upload attachment:', error);
      alert('Failed to upload attachment. Please try again.');
    } finally {
      setIsUploadingEngineerAttachment(false);
    }
  };

  const handleCustomerAttachmentUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploadingCustomerAttachment(true);
    try {
      const result = await api.uploadFile(file, 'attachment');
      const fullUrl = api.getFileUrl(result.url);
      setCustomerAttachmentUrl(fullUrl);
    } catch (error) {
      console.error('Failed to upload attachment:', error);
      alert('Failed to upload attachment. Please try again.');
    } finally {
      setIsUploadingCustomerAttachment(false);
    }
  };

  const renderCustomField = (field: CustomField) => {
    switch (field.field_type) {
      case 'text':
        return (
          <Input
            value={customFieldValues[field.name] || ''}
            onChange={(e) => setCustomFieldValues({ ...customFieldValues, [field.name]: e.target.value })}
            required={field.is_required}
          />
        );
      case 'number':
        return (
          <Input
            type="number"
            value={customFieldValues[field.name] || ''}
            onChange={(e) => setCustomFieldValues({ ...customFieldValues, [field.name]: e.target.value })}
            required={field.is_required}
          />
        );
      case 'select':
        return (
          <Select
            value={customFieldValues[field.name] || ''}
            onValueChange={(value) => setCustomFieldValues({ ...customFieldValues, [field.name]: value })}
          >
            <SelectTrigger>
              <SelectValue placeholder={`Select ${field.name}`} />
            </SelectTrigger>
            <SelectContent>
              {field.options?.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      case 'checkbox':
        return (
          <Checkbox
            checked={customFieldValues[field.name] || false}
            onCheckedChange={(checked) => setCustomFieldValues({ ...customFieldValues, [field.name]: checked })}
          />
        );
      default:
        return (
          <Input
            value={customFieldValues[field.name] || ''}
            onChange={(e) => setCustomFieldValues({ ...customFieldValues, [field.name]: e.target.value })}
          />
        );
    }
  };

  const loadApplicableFees = async (requestedTime: string) => {
    if (!productId || !changeTypeId || !selectedDate) return;
    
    setIsLoadingFees(true);
    try {
      const duration = durationHours === 0 ? parseFloat(customDuration) : durationHours;
      const requestedDateTime = `${selectedDate}T${requestedTime}:00`;
      
      const result = await api.previewApplicableFees({
        product_id: productId,
        change_type_id: changeTypeId,
        scheduled_date: requestedDateTime,
        duration_hours: duration || 1,
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

  const handleSubmitExpediteRequest = async () => {
    if (!expediteFeeAcknowledged) {
      setError('Please acknowledge the fee total before submitting');
      return;
    }

    setIsSubmittingExpedite(true);
    setError('');

    try {
      const duration = durationHours === 0 ? parseFloat(customDuration) : durationHours;
      const requestedDateTime = `${selectedDate}T${expediteRequestedTime}:00`;

      const emailList = additionalEmails
        .split(',')
        .map(e => e.trim())
        .filter(e => e.length > 0);

      await api.createExpediteRequest({
        product_id: productId!,
        change_type_id: changeTypeId!,
        order_reference: orderReference,
        customer_name: customerName,
        requested_date: requestedDateTime,
        duration_hours: duration,
        custom_fields_data: Object.keys(customFieldValues).length > 0 ? customFieldValues : undefined,
        notes: notes || undefined,
        additional_emails: emailList.length > 0 ? emailList : undefined,
        engineer_attachment_url: engineerAttachmentUrl || undefined,
        customer_attachment_url: customerAttachmentUrl || undefined,
        fee_acknowledged: true,
      });

      setShowExpediteDialog(false);
      navigate('/dashboard', { state: { message: 'Expedite request submitted successfully. You will be notified once it is reviewed.' } });
    } catch (err: any) {
      setError(err.message || 'Failed to submit expedite request');
    } finally {
      setIsSubmittingExpedite(false);
    }
  };

  const selectedProduct = products.find(p => p.id === productId);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center py-4">
            <Button variant="ghost" onClick={() => navigate('/dashboard')} className="mr-4">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
            <div>
              <h1 className="text-xl font-semibold text-gray-900">New Booking</h1>
              <p className="text-sm text-gray-500">Step {step} of 3</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg">
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

        <div className="flex mb-8">
          {[1, 2, 3].map((s) => (
            <div key={s} className="flex-1 flex items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                  s < step
                    ? 'bg-indigo-600 text-white'
                    : s === step
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-200 text-gray-600'
                }`}
              >
                {s < step ? <Check className="w-4 h-4" /> : s}
              </div>
              {s < 3 && (
                <div className={`flex-1 h-1 mx-2 ${s < step ? 'bg-indigo-600' : 'bg-gray-200'}`} />
              )}
            </div>
          ))}
        </div>

        {step === 1 && (
          <Card>
            <CardHeader>
              <CardTitle>Order Information</CardTitle>
              <CardDescription>Enter the details for your booking</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="orderReference">Order Reference *</Label>
                  <Input
                    id="orderReference"
                    value={orderReference}
                    onChange={(e) => setOrderReference(e.target.value)}
                    placeholder="e.g., ORD-2024-001"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="customerName">Customer Name *</Label>
                  <Input
                    id="customerName"
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    placeholder="Enter customer name"
                    required
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Product *</Label>
                  <Select
                    value={productId?.toString() || ''}
                    onValueChange={(value) => setProductId(parseInt(value))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select product" />
                    </SelectTrigger>
                    <SelectContent>
                      {products.map((product) => (
                        <SelectItem key={product.id} value={product.id.toString()}>
                          {product.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Change Type *</Label>
                  <Select
                    value={changeTypeId?.toString() || ''}
                    onValueChange={(value) => setChangeTypeId(parseInt(value))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select change type" />
                    </SelectTrigger>
                    <SelectContent>
                      {changeTypes.map((ct) => (
                        <SelectItem key={ct.id} value={ct.id.toString()}>
                          {ct.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {customFields.length > 0 && (
                <div className="space-y-4">
                  <h3 className="font-medium text-gray-900">Additional Information</h3>
                  {customFields.map((field) => (
                    <div key={field.id} className="space-y-2">
                      <Label>
                        {field.name} {field.is_required && '*'}
                      </Label>
                      {renderCustomField(field)}
                    </div>
                  ))}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="notes">Notes (Optional)</Label>
                <Textarea
                  id="notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Any additional notes or requirements"
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="additionalEmails">Additional Email Recipients (Optional)</Label>
                <Input
                  id="additionalEmails"
                  value={additionalEmails}
                  onChange={(e) => setAdditionalEmails(e.target.value)}
                  placeholder="Enter email addresses separated by commas"
                />
                <p className="text-xs text-gray-500">
                  These email addresses will receive booking confirmations, amendments, and cancellation notifications
                </p>
              </div>

              <div className="flex justify-end">
                <Button
                  onClick={() => {
                    if (!orderReference || !customerName || !productId || !changeTypeId) {
                      setError('Please fill in all required fields');
                      return;
                    }
                    setError('');
                    setStep(2);
                  }}
                >
                  Continue
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 2 && (
          <Card>
            <CardHeader>
              <CardTitle>Select Date & Duration</CardTitle>
              <CardDescription>Choose when you need the service</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="date">Date *</Label>
                <Input
                  id="date"
                  type="date"
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  min={new Date().toISOString().split('T')[0]}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label>Duration *</Label>
                <div className="grid grid-cols-5 gap-2">
                  {[1, 2, 3, 4].map((hours) => (
                    <Button
                      key={hours}
                      type="button"
                      variant={durationHours === hours ? 'default' : 'outline'}
                      onClick={() => {
                        setDurationHours(hours);
                        setCustomDuration('');
                      }}
                    >
                      {hours}h
                    </Button>
                  ))}
                  <Button
                    type="button"
                    variant={durationHours === 0 ? 'default' : 'outline'}
                    onClick={() => setDurationHours(0)}
                  >
                    Custom
                  </Button>
                </div>
                {durationHours === 0 && (
                  <Input
                    type="number"
                    step="0.5"
                    min="0.5"
                    max="8"
                    value={customDuration}
                    onChange={(e) => setCustomDuration(e.target.value)}
                    placeholder="Enter hours (e.g., 1.5)"
                    className="mt-2"
                  />
                )}
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox
                  id="expedited"
                  checked={isExpedited}
                  onCheckedChange={(checked) => setIsExpedited(checked as boolean)}
                />
                <Label htmlFor="expedited" className="text-sm">
                  This is an expedited request (additional fees may apply)
                </Label>
              </div>

              <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(1)}>
                  Back
                </Button>
                <Button onClick={handleCheckAvailability} disabled={isLoading}>
                  {isLoading ? 'Checking...' : 'Check Availability'}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 3 && (
          <Card>
            <CardHeader>
              <CardTitle>Select Time Slot</CardTitle>
              <CardDescription>Choose an available engineer and time</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {availability.length === 0 ? (
                <div className="text-center py-8">
                  <Calendar className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-500">No available slots found</p>
                  <Button variant="outline" onClick={() => setStep(2)} className="mt-4">
                    Try Different Date
                  </Button>
                </div>
              ) : (
                <div className="space-y-6">
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

              {selectedEngineerId && selectedSlot && (
                <div className="border-t pt-6 space-y-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Paperclip className="w-5 h-5 text-gray-500" />
                    <h3 className="font-medium text-gray-900">Email Attachments (Optional)</h3>
                  </div>
                  <p className="text-sm text-gray-500 mb-4">
                    Add attachment URLs to include specific documents in the confirmation emails. 
                    You can provide different attachments for the engineer and customer.
                  </p>
                  
                  <div className="space-y-2">
                    <Label htmlFor="engineerAttachment">Engineer Attachment</Label>
                    <div className="flex gap-2">
                      <Input
                        id="engineerAttachment"
                        value={engineerAttachmentUrl}
                        onChange={(e) => setEngineerAttachmentUrl(e.target.value)}
                        placeholder="https://example.com/engineer-document.pdf"
                        className="flex-1"
                      />
                      <div className="relative">
                        <input
                          type="file"
                          onChange={handleEngineerAttachmentUpload}
                          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                          disabled={isUploadingEngineerAttachment}
                        />
                        <Button variant="outline" disabled={isUploadingEngineerAttachment}>
                          {isUploadingEngineerAttachment ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Upload className="w-4 h-4" />
                          )}
                        </Button>
                      </div>
                    </div>
                    <p className="text-xs text-gray-500">
                      Enter a URL or upload a file. This attachment will be included in the engineer's confirmation email (e.g., technical specifications, site access details)
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="customerAttachment">Customer Attachment</Label>
                    <div className="flex gap-2">
                      <Input
                        id="customerAttachment"
                        value={customerAttachmentUrl}
                        onChange={(e) => setCustomerAttachmentUrl(e.target.value)}
                        placeholder="https://example.com/customer-document.pdf"
                        className="flex-1"
                      />
                      <div className="relative">
                        <input
                          type="file"
                          onChange={handleCustomerAttachmentUpload}
                          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                          disabled={isUploadingCustomerAttachment}
                        />
                        <Button variant="outline" disabled={isUploadingCustomerAttachment}>
                          {isUploadingCustomerAttachment ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Upload className="w-4 h-4" />
                          )}
                        </Button>
                      </div>
                    </div>
                    <p className="text-xs text-gray-500">
                      Enter a URL or upload a file. This attachment will be included in the customer's confirmation email (e.g., service agreement, preparation instructions)
                    </p>
                  </div>
                </div>
              )}

              <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(2)}>
                  Back
                </Button>
                <Button
                  onClick={handleSubmitBooking}
                  disabled={isLoading || !selectedEngineerId || !selectedSlot}
                >
                  {isLoading ? 'Creating Booking...' : 'Confirm Booking'}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </main>

      {/* Expedite Request Dialog */}
      <Dialog open={showExpediteDialog} onOpenChange={setShowExpediteDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Submit Special Resourcing Request</DialogTitle>
            <DialogDescription>
              Request special resourcing for {selectedDate}. Your request will be reviewed by an administrator.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-lg space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Order Reference:</span>
                <span className="font-medium">{orderReference}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Customer:</span>
                <span className="font-medium">{customerName}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Product:</span>
                <span className="font-medium">{selectedProduct?.name || '-'}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Date:</span>
                <span className="font-medium">{selectedDate}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Duration:</span>
                <span className="font-medium">{durationHours === 0 ? customDuration : durationHours} hours</span>
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
              onClick={handleSubmitExpediteRequest}
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
