import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import { Product, ChangeType, Engineer, CustomField, Fee, SystemConfig, User, DashboardStats, EmailTemplate, CalendarEventTemplate, TemplateType, ExpediteRequest, ExpediteRequestStatus } from '../types';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Checkbox } from '../components/ui/checkbox';
import { 
  ArrowLeft, Plus, Edit, Trash2, Users,
  Calendar, UserCheck, Clock, Settings, Mail, CalendarDays, Upload, Loader2, AlertCircle, Download, BarChart3, FileSpreadsheet
} from 'lucide-react';
import RosterPatternBuilder from '../components/RosterPatternBuilder';
import * as XLSX from 'xlsx';

export default function AdminPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [changeTypes, setChangeTypes] = useState<ChangeType[]>([]);
  const [engineers, setEngineers] = useState<Engineer[]>([]);
  const [customFields, setCustomFields] = useState<CustomField[]>([]);
  const [fees, setFees] = useState<Fee[]>([]);
  const [configs, setConfigs] = useState<SystemConfig[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const [showProductDialog, setShowProductDialog] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [productName, setProductName] = useState('');
  const [productDescription, setProductDescription] = useState('');
  const [productExpediteFee, setProductExpediteFee] = useState('');
  const [productExpediteContactEmails, setProductExpediteContactEmails] = useState('');

  const [showChangeTypeDialog, setShowChangeTypeDialog] = useState(false);
  const [editingChangeType, setEditingChangeType] = useState<ChangeType | null>(null);
  const [changeTypeName, setChangeTypeName] = useState('');
  const [changeTypeDescription, setChangeTypeDescription] = useState('');

  const [showEngineerDialog, setShowEngineerDialog] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [engineerEmail, setEngineerEmail] = useState('');
  const [workingHoursStart, setWorkingHoursStart] = useState('09:00');
  const [workingHoursEnd, setWorkingHoursEnd] = useState('17:00');

  const [showFieldDialog, setShowFieldDialog] = useState(false);
  const [editingField, setEditingField] = useState<CustomField | null>(null);
  const [fieldName, setFieldName] = useState('');
  const [fieldType, setFieldType] = useState('text');
  const [fieldRequired, setFieldRequired] = useState(false);
  const [fieldOptions, setFieldOptions] = useState('');

  const [showFeeDialog, setShowFeeDialog] = useState(false);
  const [editingFee, setEditingFee] = useState<Fee | null>(null);
  const [feeName, setFeeName] = useState('');
  const [feeType, setFeeType] = useState('');
  const [feeAmount, setFeeAmount] = useState('');
  const [feeDescription, setFeeDescription] = useState('');

  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [configKey, setConfigKey] = useState('');
  const [configValue, setConfigValue] = useState('');
  const [configDescription, setConfigDescription] = useState('');

  const [sharepointSiteUrl, setSharepointSiteUrl] = useState('');
  const [sharepointSiteId, setSharepointSiteId] = useState('');
  const [sharepointListId, setSharepointListId] = useState('');
  const [microsoftClientId, setMicrosoftClientId] = useState('');
  const [microsoftTenantId, setMicrosoftTenantId] = useState('');
  const [isSavingSharepoint, setIsSavingSharepoint] = useState(false);
  const [sharepointStatus, setSharepointStatus] = useState('');

  const [emailTemplates, setEmailTemplates] = useState<EmailTemplate[]>([]);
  const [calendarTemplates, setCalendarTemplates] = useState<CalendarEventTemplate[]>([]);
  const [templatePlaceholders, setTemplatePlaceholders] = useState<string[]>([]);
  
  const [showEmailTemplateDialog, setShowEmailTemplateDialog] = useState(false);
  const [editingEmailTemplate, setEditingEmailTemplate] = useState<EmailTemplate | null>(null);
  const [emailTemplateName, setEmailTemplateName] = useState('');
  const [emailTemplateType, setEmailTemplateType] = useState<TemplateType>('confirmation');
  const [emailTemplateSubject, setEmailTemplateSubject] = useState('');
  const [emailTemplateBody, setEmailTemplateBody] = useState('');
  const [emailTemplateSendToEngineer, setEmailTemplateSendToEngineer] = useState(true);
  const [emailTemplateSendToCustomer, setEmailTemplateSendToCustomer] = useState(true);
  const [emailTemplateAdditionalEmails, setEmailTemplateAdditionalEmails] = useState('');
  const [emailTemplateLogoUrl, setEmailTemplateLogoUrl] = useState('');
  const [emailTemplateIsDefault, setEmailTemplateIsDefault] = useState(false);
  const [isUploadingLogo, setIsUploadingLogo] = useState(false);

  const [showCalendarTemplateDialog, setShowCalendarTemplateDialog] = useState(false);
  const [editingCalendarTemplate, setEditingCalendarTemplate] = useState<CalendarEventTemplate | null>(null);
  const [calendarTemplateName, setCalendarTemplateName] = useState('');
  const [calendarTemplateType, setCalendarTemplateType] = useState<TemplateType>('confirmation');
  const [calendarTemplateTitle, setCalendarTemplateTitle] = useState('');
  const [calendarTemplateBody, setCalendarTemplateBody] = useState('');
  const [calendarTemplateIncludeCustomer, setCalendarTemplateIncludeCustomer] = useState(false);
  const [calendarTemplateAdditionalAttendees, setCalendarTemplateAdditionalAttendees] = useState('');
  const [calendarTemplateIsDefault, setCalendarTemplateIsDefault] = useState(false);

  const emailSubjectRef = useRef<HTMLInputElement>(null);
  const emailBodyRef = useRef<HTMLTextAreaElement>(null);
  const calendarTitleRef = useRef<HTMLInputElement>(null);
  const calendarBodyRef = useRef<HTMLTextAreaElement>(null);
  const [activeField, setActiveField] = useState<'emailSubject' | 'emailBody' | 'calendarTitle' | 'calendarBody' | null>(null);

  // Tab state for programmatic navigation
  const [activeTab, setActiveTab] = useState('products');

  // Reporting state
  const [reportType, setReportType] = useState<string>('bookings');
  const [reportStartDate, setReportStartDate] = useState('');
  const [reportEndDate, setReportEndDate] = useState('');
  const [reportData, setReportData] = useState<any[]>([]);
  const [revenueSummary, setRevenueSummary] = useState<any>(null);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [reportProductFilter, setReportProductFilter] = useState<string>('');
  const [reportEngineerFilter, setReportEngineerFilter] = useState<string>('');
  const [reportStatusFilter, setReportStatusFilter] = useState<string>('');

  // Expedite Requests state
  const [expediteRequests, setExpediteRequests] = useState<ExpediteRequest[]>([]);
  const [expediteStatusFilter, setExpediteStatusFilter] = useState<string>('all');
  const [selectedExpediteRequest, setSelectedExpediteRequest] = useState<ExpediteRequest | null>(null);
  const [showExpediteDetailDialog, setShowExpediteDetailDialog] = useState(false);
  const [showApproveDialog, setShowApproveDialog] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [approveEngineerId, setApproveEngineerId] = useState<number | null>(null);
  const [approveScheduledDate, setApproveScheduledDate] = useState('');
  const [approveAdminNotes, setApproveAdminNotes] = useState('');
  const [rejectAdminNotes, setRejectAdminNotes] = useState('');
  const [isProcessingExpedite, setIsProcessingExpedite] = useState(false);

  useEffect(() => {
    if (user?.role !== 'admin') {
      navigate('/dashboard');
      return;
    }
    loadAllData();
  }, [user, navigate]);

  const loadAllData = async () => {
    setIsLoading(true);
    try {
      const [statsData, productsData, changeTypesData, engineersData, fieldsData, feesData, configsData, usersData, emailTemplatesData, calendarTemplatesData, placeholdersData] = await Promise.all([
        api.getDashboardStats(),
        api.getProducts(),
        api.getChangeTypes(),
        api.getEngineers(),
        api.getCustomFields(),
        api.getFees(),
        api.getSystemConfig(),
        api.getAllUsers(),
        api.getEmailTemplates(),
        api.getCalendarTemplates(),
        api.getTemplatePlaceholders(),
      ]);
      
      setStats(statsData as DashboardStats);
      setProducts(productsData as Product[]);
      setChangeTypes(changeTypesData as ChangeType[]);
      setEngineers(engineersData as Engineer[]);
      setCustomFields(fieldsData as CustomField[]);
      setFees(feesData as Fee[]);
      setConfigs(configsData as SystemConfig[]);
      setUsers(usersData as User[]);
      setEmailTemplates(emailTemplatesData as EmailTemplate[]);
      setCalendarTemplates(calendarTemplatesData as CalendarEventTemplate[]);
      setTemplatePlaceholders((placeholdersData as { booking_fields: string[] }).booking_fields);

      const configsList = configsData as SystemConfig[];
      const spSiteUrl = configsList.find(c => c.key === 'sharepoint_site_url');
      const spSiteId = configsList.find(c => c.key === 'sharepoint_site_id');
      const spListId = configsList.find(c => c.key === 'sharepoint_list_id');
      const msClientId = configsList.find(c => c.key === 'microsoft_client_id');
      const msTenantId = configsList.find(c => c.key === 'microsoft_tenant_id');
      
      if (spSiteUrl) setSharepointSiteUrl(spSiteUrl.value);
      if (spSiteId) setSharepointSiteId(spSiteId.value);
      if (spListId) setSharepointListId(spListId.value);
      if (msClientId) setMicrosoftClientId(msClientId.value);
      if (msTenantId) setMicrosoftTenantId(msTenantId.value);
    } catch (err: any) {
      setError(err.message || 'Failed to load data');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveProduct = async () => {
    try {
      const expediteFee = productExpediteFee ? parseFloat(productExpediteFee) : 0;
      const expediteEmails = productExpediteContactEmails
        ? productExpediteContactEmails.split(',').map(e => e.trim()).filter(e => e)
        : [];
      
      if (editingProduct) {
        await api.updateProduct(editingProduct.id, productName, productDescription, expediteFee, expediteEmails);
      } else {
        await api.createProduct(productName, productDescription, expediteFee, expediteEmails);
      }
      setShowProductDialog(false);
      setEditingProduct(null);
      setProductName('');
      setProductDescription('');
      setProductExpediteFee('');
      setProductExpediteContactEmails('');
      loadAllData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteProduct = async (id: number) => {
    if (confirm('Are you sure you want to delete this product?')) {
      try {
        await api.deleteProduct(id);
        loadAllData();
      } catch (err: any) {
        setError(err.message);
      }
    }
  };

  const handleSaveChangeType = async () => {
    try {
      if (editingChangeType) {
        await api.updateChangeType(editingChangeType.id, changeTypeName, changeTypeDescription);
      } else {
        await api.createChangeType(changeTypeName, changeTypeDescription);
      }
      setShowChangeTypeDialog(false);
      setEditingChangeType(null);
      setChangeTypeName('');
      setChangeTypeDescription('');
      loadAllData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteChangeType = async (id: number) => {
    if (confirm('Are you sure you want to delete this change type?')) {
      try {
        await api.deleteChangeType(id);
        loadAllData();
      } catch (err: any) {
        setError(err.message);
      }
    }
  };

  const handleCreateEngineer = async () => {
    if (!selectedUserId || !engineerEmail) return;
    try {
      await api.createEngineer(selectedUserId, engineerEmail, workingHoursStart, workingHoursEnd);
      setShowEngineerDialog(false);
      setSelectedUserId(null);
      setEngineerEmail('');
      setWorkingHoursStart('09:00');
      setWorkingHoursEnd('17:00');
      loadAllData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleSaveCustomField = async () => {
    try {
      const options = fieldType === 'select' ? fieldOptions.split(',').map(o => o.trim()).filter(o => o) : undefined;
      const data = {
        name: fieldName,
        field_type: fieldType,
        is_required: fieldRequired,
        options,
        display_order: customFields.length,
      };
      
      if (editingField) {
        await api.updateCustomField(editingField.id, data);
      } else {
        await api.createCustomField(data);
      }
      setShowFieldDialog(false);
      setEditingField(null);
      setFieldName('');
      setFieldType('text');
      setFieldRequired(false);
      setFieldOptions('');
      loadAllData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteCustomField = async (id: number) => {
    if (confirm('Are you sure you want to delete this custom field?')) {
      try {
        await api.deleteCustomField(id);
        loadAllData();
      } catch (err: any) {
        setError(err.message);
      }
    }
  };

  const handleSaveFee = async () => {
    try {
      const data = {
        name: feeName,
        fee_type: feeType,
        amount: parseFloat(feeAmount),
        description: feeDescription || undefined,
      };
      
      if (editingFee) {
        await api.updateFee(editingFee.id, data);
      } else {
        await api.createFee(data);
      }
      setShowFeeDialog(false);
      setEditingFee(null);
      setFeeName('');
      setFeeType('');
      setFeeAmount('');
      setFeeDescription('');
      loadAllData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteFee = async (id: number) => {
    if (confirm('Are you sure you want to delete this fee?')) {
      try {
        await api.deleteFee(id);
        loadAllData();
      } catch (err: any) {
        setError(err.message);
      }
    }
  };

  const handleSaveConfig = async () => {
    try {
      await api.setSystemConfig(configKey, configValue, configDescription);
      setShowConfigDialog(false);
      setConfigKey('');
      setConfigValue('');
      setConfigDescription('');
      loadAllData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleUpdateUserRole = async (userId: number, role: string) => {
    try {
      await api.updateUserRole(userId, role);
      loadAllData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleSaveSharepointConfig = async () => {
    setIsSavingSharepoint(true);
    setSharepointStatus('');
    try {
      await Promise.all([
        api.setSystemConfig('sharepoint_site_url', sharepointSiteUrl, 'SharePoint site URL'),
        api.setSystemConfig('sharepoint_site_id', sharepointSiteId, 'SharePoint site ID'),
        api.setSystemConfig('sharepoint_list_id', sharepointListId, 'SharePoint list ID for bookings'),
        api.setSystemConfig('microsoft_client_id', microsoftClientId, 'Microsoft Azure AD Client ID'),
        api.setSystemConfig('microsoft_tenant_id', microsoftTenantId, 'Microsoft Azure AD Tenant ID'),
      ]);
      setSharepointStatus('Configuration saved successfully!');
      loadAllData();
    } catch (err: any) {
      setError(err.message);
      setSharepointStatus('Failed to save configuration');
    } finally {
      setIsSavingSharepoint(false);
    }
  };

  const resetEmailTemplateForm = () => {
    setEditingEmailTemplate(null);
    setEmailTemplateName('');
    setEmailTemplateType('confirmation');
    setEmailTemplateSubject('');
    setEmailTemplateBody('');
    setEmailTemplateSendToEngineer(true);
    setEmailTemplateSendToCustomer(true);
    setEmailTemplateAdditionalEmails('');
    setEmailTemplateLogoUrl('');
    setEmailTemplateIsDefault(false);
    setActiveField(null);
  };

  const openEditEmailTemplate = (template: EmailTemplate) => {
    setEditingEmailTemplate(template);
    setEmailTemplateName(template.name);
    setEmailTemplateType(template.template_type);
    setEmailTemplateSubject(template.subject);
    setEmailTemplateBody(template.body_html);
    setEmailTemplateSendToEngineer(template.send_to_engineer);
    setEmailTemplateSendToCustomer(template.send_to_customer);
    setEmailTemplateAdditionalEmails(template.additional_emails?.join(', ') || '');
    setEmailTemplateLogoUrl(template.logo_url || '');
    setEmailTemplateIsDefault(template.is_default);
    setShowEmailTemplateDialog(true);
  };

  const handleSaveEmailTemplate = async () => {
    try {
      const additionalEmails = emailTemplateAdditionalEmails
        .split(',')
        .map(e => e.trim())
        .filter(e => e);
      
      const data = {
        name: emailTemplateName,
        template_type: emailTemplateType,
        subject: emailTemplateSubject,
        body_html: emailTemplateBody,
        logo_url: emailTemplateLogoUrl || undefined,
        send_to_engineer: emailTemplateSendToEngineer,
        send_to_customer: emailTemplateSendToCustomer,
        additional_emails: additionalEmails.length > 0 ? additionalEmails : undefined,
        is_default: emailTemplateIsDefault,
      };

      if (editingEmailTemplate) {
        await api.updateEmailTemplate(editingEmailTemplate.id, data);
      } else {
        await api.createEmailTemplate(data);
      }
      setShowEmailTemplateDialog(false);
      resetEmailTemplateForm();
      loadAllData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteEmailTemplate = async (id: number) => {
    if (confirm('Are you sure you want to delete this email template?')) {
      try {
        await api.deleteEmailTemplate(id);
        loadAllData();
      } catch (err: any) {
        setError(err.message);
      }
    }
  };

  const resetCalendarTemplateForm = () => {
    setEditingCalendarTemplate(null);
    setCalendarTemplateName('');
    setCalendarTemplateType('confirmation');
    setCalendarTemplateTitle('');
    setCalendarTemplateBody('');
    setCalendarTemplateIncludeCustomer(false);
    setCalendarTemplateAdditionalAttendees('');
    setCalendarTemplateIsDefault(false);
  };

  const openEditCalendarTemplate = (template: CalendarEventTemplate) => {
    setEditingCalendarTemplate(template);
    setCalendarTemplateName(template.name);
    setCalendarTemplateType(template.template_type);
    setCalendarTemplateTitle(template.event_title);
    setCalendarTemplateBody(template.event_body || '');
    setCalendarTemplateIncludeCustomer(template.include_customer_as_attendee);
    setCalendarTemplateAdditionalAttendees(template.additional_attendees?.join(', ') || '');
    setCalendarTemplateIsDefault(template.is_default);
    setShowCalendarTemplateDialog(true);
  };

  const handleSaveCalendarTemplate = async () => {
    try {
      const additionalAttendees = calendarTemplateAdditionalAttendees
        .split(',')
        .map(e => e.trim())
        .filter(e => e);
      
      const data = {
        name: calendarTemplateName,
        template_type: calendarTemplateType,
        event_title: calendarTemplateTitle,
        event_body: calendarTemplateBody || undefined,
        include_customer_as_attendee: calendarTemplateIncludeCustomer,
        additional_attendees: additionalAttendees.length > 0 ? additionalAttendees : undefined,
        is_default: calendarTemplateIsDefault,
      };

      if (editingCalendarTemplate) {
        await api.updateCalendarTemplate(editingCalendarTemplate.id, data);
      } else {
        await api.createCalendarTemplate(data);
      }
      setShowCalendarTemplateDialog(false);
      resetCalendarTemplateForm();
      loadAllData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteCalendarTemplate = async (id: number) => {
    if (confirm('Are you sure you want to delete this calendar template?')) {
      try {
        await api.deleteCalendarTemplate(id);
        loadAllData();
      } catch (err: any) {
        setError(err.message);
      }
    }
  };

  const handleLogoUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploadingLogo(true);
    try {
      const result = await api.uploadFile(file, 'logo');
      const fullUrl = api.getFileUrl(result.url);
      setEmailTemplateLogoUrl(fullUrl);
    } catch (error) {
      console.error('Failed to upload logo:', error);
      alert('Failed to upload logo. Please try again.');
    } finally {
      setIsUploadingLogo(false);
    }
  };

  const insertPlaceholderAtCursor = (placeholder: string) => {
    const target = activeField;
    if (!target) return;

    let ref: React.RefObject<HTMLInputElement | HTMLTextAreaElement | null>;
    let setValue: React.Dispatch<React.SetStateAction<string>>;
    let currentValue: string;

    switch (target) {
      case 'emailSubject':
        ref = emailSubjectRef;
        setValue = setEmailTemplateSubject;
        currentValue = emailTemplateSubject;
        break;
      case 'emailBody':
        ref = emailBodyRef;
        setValue = setEmailTemplateBody;
        currentValue = emailTemplateBody;
        break;
      case 'calendarTitle':
        ref = calendarTitleRef;
        setValue = setCalendarTemplateTitle;
        currentValue = calendarTemplateTitle;
        break;
      case 'calendarBody':
        ref = calendarBodyRef;
        setValue = setCalendarTemplateBody;
        currentValue = calendarTemplateBody;
        break;
      default:
        return;
    }

    const element = ref.current;
    if (element) {
      const start = element.selectionStart || 0;
      const end = element.selectionEnd || 0;
      const newValue = currentValue.substring(0, start) + placeholder + currentValue.substring(end);
      setValue(newValue);
      
      setTimeout(() => {
        element.focus();
        const newCursorPos = start + placeholder.length;
        element.setSelectionRange(newCursorPos, newCursorPos);
      }, 0);
    } else {
      setValue(prev => prev + placeholder);
    }
  };

  const nonEngineerUsers = users.filter(u => !engineers.some(e => e.user_id === u.id));

  // Expedite Request handlers
  const loadExpediteRequests = async () => {
    try {
      const filter = expediteStatusFilter === 'all' ? undefined : expediteStatusFilter;
      const data = await api.getExpediteRequests(filter);
      setExpediteRequests(data as ExpediteRequest[]);
    } catch (err: any) {
      console.error('Failed to load expedite requests:', err);
    }
  };

  useEffect(() => {
    loadExpediteRequests();
  }, [expediteStatusFilter]);

  const handleApproveExpediteRequest = async () => {
    if (!selectedExpediteRequest || !approveEngineerId || !approveScheduledDate) return;
    
    setIsProcessingExpedite(true);
    try {
      await api.approveExpediteRequest(selectedExpediteRequest.id, {
        assigned_engineer_id: approveEngineerId,
        scheduled_date: approveScheduledDate,
        admin_notes: approveAdminNotes || undefined,
      });
      setShowApproveDialog(false);
      setShowExpediteDetailDialog(false);
      setSelectedExpediteRequest(null);
      setApproveEngineerId(null);
      setApproveScheduledDate('');
      setApproveAdminNotes('');
      loadExpediteRequests();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsProcessingExpedite(false);
    }
  };

  const handleRejectExpediteRequest = async () => {
    if (!selectedExpediteRequest) return;
    
    setIsProcessingExpedite(true);
    try {
      await api.rejectExpediteRequest(selectedExpediteRequest.id, {
        admin_notes: rejectAdminNotes || undefined,
      });
      setShowRejectDialog(false);
      setShowExpediteDetailDialog(false);
      setSelectedExpediteRequest(null);
      setRejectAdminNotes('');
      loadExpediteRequests();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsProcessingExpedite(false);
    }
  };

  const getStatusBadgeColor = (status: ExpediteRequestStatus) => {
    switch (status) {
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'approved': return 'bg-green-100 text-green-800';
      case 'rejected': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const loadReport = async () => {
    setIsLoadingReport(true);
    try {
      const filters: any = {};
      if (reportStartDate) filters.start_date = reportStartDate;
      if (reportEndDate) filters.end_date = reportEndDate;
      
      let data: any[] = [];
      
      switch (reportType) {
        case 'bookings':
          if (reportProductFilter && reportProductFilter !== 'all') filters.product_id = parseInt(reportProductFilter);
          if (reportEngineerFilter && reportEngineerFilter !== 'all') filters.engineer_id = parseInt(reportEngineerFilter);
          if (reportStatusFilter && reportStatusFilter !== 'all') filters.status = reportStatusFilter;
          data = await api.getBookingsReport(filters) as any[];
          break;
        case 'engineers':
          data = await api.getEngineersUtilizationReport(filters) as any[];
          break;
        case 'products':
          data = await api.getProductsSummaryReport(filters) as any[];
          break;
        case 'expedite':
          data = await api.getExpediteRequestsSummaryReport(filters) as any[];
          break;
        case 'revenue':
          const revenue = await api.getRevenueSummaryReport(filters);
          setRevenueSummary(revenue);
          data = [];
          break;
      }
      
      setReportData(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoadingReport(false);
    }
  };

  const exportToExcel = () => {
    if (reportData.length === 0 && reportType !== 'revenue') {
      setError('No data to export');
      return;
    }
    
    let exportData: any[] = [];
    let sheetName = 'Report';
    
    switch (reportType) {
      case 'bookings':
        sheetName = 'Bookings Report';
        exportData = reportData.map(b => ({
          'ID': b.id,
          'Order Reference': b.order_reference,
          'Customer Name': b.customer_name,
          'Scheduled Date': b.scheduled_date,
          'Duration (Hours)': b.duration_hours,
          'Status': b.status,
          'Product': b.product_name,
          'Change Type': b.change_type_name,
          'Engineer': b.engineer_name,
          'Booker': b.booker_name,
          'Cancellation Fee': b.cancellation_fee,
          'Expedite Fee': b.expedite_fee,
          'Created At': b.created_at,
        }));
        break;
      case 'engineers':
        sheetName = 'Engineer Utilization';
        exportData = reportData.map(e => ({
          'Engineer ID': e.engineer_id,
          'Engineer Name': e.engineer_name,
          'Calendar Email': e.calendar_email,
          'Available': e.is_available ? 'Yes' : 'No',
          'Total Bookings': e.total_bookings,
          'Completed Bookings': e.completed_bookings,
          'Total Hours': e.total_hours,
        }));
        break;
      case 'products':
        sheetName = 'Products Summary';
        exportData = reportData.map(p => ({
          'Product ID': p.product_id,
          'Product Name': p.product_name,
          'Total Bookings': p.total_bookings,
          'Total Hours': p.total_hours,
          'Expedite Fees': p.total_expedite_fees,
          'Cancellation Fees': p.total_cancellation_fees,
        }));
        break;
      case 'expedite':
        sheetName = 'Expedite Requests';
        exportData = reportData.map(r => ({
          'ID': r.id,
          'Order Reference': r.order_reference,
          'Customer Name': r.customer_name,
          'Requested Date': r.requested_date,
          'Duration (Hours)': r.duration_hours,
          'Status': r.status,
          'Expedite Fee': r.expedite_fee,
          'Fee Acknowledged': r.fee_acknowledged ? 'Yes' : 'No',
          'Product': r.product_name,
          'Change Type': r.change_type_name,
          'Requester': r.requester_name,
          'Assigned Engineer': r.assigned_engineer_name,
          'Admin Notes': r.admin_notes,
          'Created At': r.created_at,
        }));
        break;
      case 'revenue':
        sheetName = 'Revenue Summary';
        if (revenueSummary) {
          exportData = [
            { 'Metric': 'Total Bookings', 'Value': revenueSummary.total_bookings },
            { 'Metric': 'Total Expedite Fees', 'Value': revenueSummary.total_expedite_fees },
            { 'Metric': 'Total Cancellation Fees', 'Value': revenueSummary.total_cancellation_fees },
            { 'Metric': 'Approved Expedite Requests', 'Value': revenueSummary.approved_expedite_requests },
            { 'Metric': 'Expedite Request Fees', 'Value': revenueSummary.expedite_request_fees },
          ];
          if (revenueSummary.status_breakdown) {
            Object.entries(revenueSummary.status_breakdown).forEach(([status, count]) => {
              exportData.push({ 'Metric': `Bookings - ${status}`, 'Value': count });
            });
          }
        }
        break;
    }
    
    const worksheet = XLSX.utils.json_to_sheet(exportData);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, sheetName);
    
    const dateStr = new Date().toISOString().split('T')[0];
    XLSX.writeFile(workbook, `${sheetName.replace(/\s+/g, '_')}_${dateStr}.xlsx`);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-500">Loading admin panel...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center py-4">
            <Button variant="ghost" onClick={() => navigate('/dashboard')} className="mr-4">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
            <div>
              <h1 className="text-xl font-semibold text-gray-900">Admin Configuration</h1>
              <p className="text-sm text-gray-500">Manage system settings and data</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg">
            {error}
            <button onClick={() => setError('')} className="ml-2 text-red-900 font-medium">Dismiss</button>
          </div>
        )}

        {stats && (
          <div className="grid gap-4 md:grid-cols-5 mb-8">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center">
                  <Calendar className="w-8 h-8 text-indigo-600 mr-3" />
                  <div>
                    <p className="text-2xl font-bold">{stats.total_bookings}</p>
                    <p className="text-sm text-gray-500">Total Bookings</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center">
                  <Clock className="w-8 h-8 text-yellow-600 mr-3" />
                  <div>
                    <p className="text-2xl font-bold">{stats.pending_bookings}</p>
                    <p className="text-sm text-gray-500">Pending</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center">
                  <UserCheck className="w-8 h-8 text-green-600 mr-3" />
                  <div>
                    <p className="text-2xl font-bold">{stats.confirmed_bookings}</p>
                    <p className="text-sm text-gray-500">Confirmed</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center">
                  <Users className="w-8 h-8 text-blue-600 mr-3" />
                  <div>
                    <p className="text-2xl font-bold">{stats.total_engineers}</p>
                    <p className="text-sm text-gray-500">Engineers</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center">
                  <UserCheck className="w-8 h-8 text-teal-600 mr-3" />
                  <div>
                    <p className="text-2xl font-bold">{stats.available_engineers}</p>
                    <p className="text-sm text-gray-500">Available</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card 
              className="cursor-pointer hover:shadow-md transition-shadow border-amber-200 bg-amber-50"
              onClick={() => setActiveTab('expedite-requests')}
            >
              <CardContent className="pt-6">
                <div className="flex items-center">
                  <AlertCircle className="w-8 h-8 text-amber-600 mr-3" />
                  <div>
                    <p className="text-2xl font-bold">{stats.pending_expedite_requests}</p>
                    <p className="text-sm text-gray-500">Expedite Requests</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-11">
            <TabsTrigger value="products">Products</TabsTrigger>
            <TabsTrigger value="change-types">Change Types</TabsTrigger>
            <TabsTrigger value="engineers">Engineers</TabsTrigger>
            <TabsTrigger value="roster-patterns">Rosters</TabsTrigger>
            <TabsTrigger value="fields">Custom Fields</TabsTrigger>
            <TabsTrigger value="fees">Fees</TabsTrigger>
            <TabsTrigger value="expedite-requests">Expedite</TabsTrigger>
            <TabsTrigger value="reports">Reports</TabsTrigger>
            <TabsTrigger value="email-templates">Email</TabsTrigger>
            <TabsTrigger value="calendar-templates">Calendar</TabsTrigger>
            <TabsTrigger value="config">Settings</TabsTrigger>
          </TabsList>

          <TabsContent value="products">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Products</CardTitle>
                  <CardDescription>Manage available products for bookings</CardDescription>
                </div>
                <Dialog open={showProductDialog} onOpenChange={setShowProductDialog}>
                  <DialogTrigger asChild>
                    <Button onClick={() => { setEditingProduct(null); setProductName(''); setProductDescription(''); setProductExpediteFee(''); setProductExpediteContactEmails(''); }}>
                      <Plus className="w-4 h-4 mr-2" />
                      Add Product
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>{editingProduct ? 'Edit Product' : 'Add Product'}</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label>Name</Label>
                        <Input value={productName} onChange={(e) => setProductName(e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Description</Label>
                        <Textarea value={productDescription} onChange={(e) => setProductDescription(e.target.value)} />
                      </div>
                      <div className="border-t pt-4 mt-4">
                        <h4 className="font-medium mb-3">Expedite Request Settings</h4>
                        <div className="space-y-4">
                          <div className="space-y-2">
                            <Label>Expedite Fee</Label>
                            <Input 
                              type="number" 
                              step="0.01"
                              placeholder="0.00"
                              value={productExpediteFee} 
                              onChange={(e) => setProductExpediteFee(e.target.value)} 
                            />
                            <p className="text-sm text-muted-foreground">Fee charged for expedite requests on this product</p>
                          </div>
                          <div className="space-y-2">
                            <Label>Expedite Contact Emails</Label>
                            <Input 
                              placeholder="email1@example.com, email2@example.com"
                              value={productExpediteContactEmails} 
                              onChange={(e) => setProductExpediteContactEmails(e.target.value)} 
                            />
                            <p className="text-sm text-muted-foreground">Comma-separated email addresses to notify when expedite requests are submitted</p>
                          </div>
                        </div>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowProductDialog(false)}>Cancel</Button>
                      <Button onClick={handleSaveProduct}>Save</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {products.map((product) => (
                      <TableRow key={product.id}>
                        <TableCell className="font-medium">{product.name}</TableCell>
                        <TableCell>{product.description || '-'}</TableCell>
                        <TableCell>{new Date(product.created_at).toLocaleDateString()}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditingProduct(product);
                              setProductName(product.name);
                              setProductDescription(product.description || '');
                              setProductExpediteFee(product.expedite_fee?.toString() || '');
                              setProductExpediteContactEmails(product.expedite_contact_emails?.join(', ') || '');
                              setShowProductDialog(true);
                            }}
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDeleteProduct(product.id)}>
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="change-types">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Change Types</CardTitle>
                  <CardDescription>Manage types of changes/services</CardDescription>
                </div>
                <Dialog open={showChangeTypeDialog} onOpenChange={setShowChangeTypeDialog}>
                  <DialogTrigger asChild>
                    <Button onClick={() => { setEditingChangeType(null); setChangeTypeName(''); setChangeTypeDescription(''); }}>
                      <Plus className="w-4 h-4 mr-2" />
                      Add Change Type
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>{editingChangeType ? 'Edit Change Type' : 'Add Change Type'}</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label>Name</Label>
                        <Input value={changeTypeName} onChange={(e) => setChangeTypeName(e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Description</Label>
                        <Textarea value={changeTypeDescription} onChange={(e) => setChangeTypeDescription(e.target.value)} />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowChangeTypeDialog(false)}>Cancel</Button>
                      <Button onClick={handleSaveChangeType}>Save</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {changeTypes.map((ct) => (
                      <TableRow key={ct.id}>
                        <TableCell className="font-medium">{ct.name}</TableCell>
                        <TableCell>{ct.description || '-'}</TableCell>
                        <TableCell>{new Date(ct.created_at).toLocaleDateString()}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditingChangeType(ct);
                              setChangeTypeName(ct.name);
                              setChangeTypeDescription(ct.description || '');
                              setShowChangeTypeDialog(true);
                            }}
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDeleteChangeType(ct.id)}>
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="engineers">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Engineers</CardTitle>
                  <CardDescription>Manage service engineers and their skills</CardDescription>
                </div>
                <Dialog open={showEngineerDialog} onOpenChange={setShowEngineerDialog}>
                  <DialogTrigger asChild>
                    <Button>
                      <Plus className="w-4 h-4 mr-2" />
                      Add Engineer
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Add Engineer</DialogTitle>
                      <DialogDescription>Select a user to make them an engineer</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label>User</Label>
                        <Select value={selectedUserId?.toString() || ''} onValueChange={(v) => setSelectedUserId(parseInt(v))}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select user" />
                          </SelectTrigger>
                          <SelectContent>
                            {nonEngineerUsers.map((u) => (
                              <SelectItem key={u.id} value={u.id.toString()}>
                                {u.full_name} ({u.email})
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Calendar Email (Outlook)</Label>
                        <Input value={engineerEmail} onChange={(e) => setEngineerEmail(e.target.value)} placeholder="engineer@company.com" />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label>Working Hours Start</Label>
                          <Input type="time" value={workingHoursStart} onChange={(e) => setWorkingHoursStart(e.target.value)} />
                        </div>
                        <div className="space-y-2">
                          <Label>Working Hours End</Label>
                          <Input type="time" value={workingHoursEnd} onChange={(e) => setWorkingHoursEnd(e.target.value)} />
                        </div>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowEngineerDialog(false)}>Cancel</Button>
                      <Button onClick={handleCreateEngineer}>Add Engineer</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Calendar Email</TableHead>
                      <TableHead>Working Hours</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {engineers.map((engineer) => (
                      <TableRow key={engineer.id}>
                        <TableCell className="font-medium">{engineer.user?.full_name || 'Unknown'}</TableCell>
                        <TableCell>{engineer.calendar_email}</TableCell>
                        <TableCell>{engineer.working_hours_start} - {engineer.working_hours_end}</TableCell>
                        <TableCell>
                          <Badge className={engineer.is_available ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                            {engineer.is_available ? 'Available' : 'Unavailable'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate(`/admin/engineer/${engineer.id}`)}
                          >
                            <Settings className="w-4 h-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="roster-patterns">
            <RosterPatternBuilder />
          </TabsContent>

          <TabsContent value="fields">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Custom Fields</CardTitle>
                  <CardDescription>Add custom fields to the booking form</CardDescription>
                </div>
                <Dialog open={showFieldDialog} onOpenChange={setShowFieldDialog}>
                  <DialogTrigger asChild>
                    <Button onClick={() => { setEditingField(null); setFieldName(''); setFieldType('text'); setFieldRequired(false); setFieldOptions(''); }}>
                      <Plus className="w-4 h-4 mr-2" />
                      Add Field
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>{editingField ? 'Edit Custom Field' : 'Add Custom Field'}</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label>Field Name</Label>
                        <Input value={fieldName} onChange={(e) => setFieldName(e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Field Type</Label>
                        <Select value={fieldType} onValueChange={setFieldType}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="text">Text</SelectItem>
                            <SelectItem value="number">Number</SelectItem>
                            <SelectItem value="select">Dropdown</SelectItem>
                            <SelectItem value="checkbox">Checkbox</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      {fieldType === 'select' && (
                        <div className="space-y-2">
                          <Label>Options (comma-separated)</Label>
                          <Input value={fieldOptions} onChange={(e) => setFieldOptions(e.target.value)} placeholder="Option 1, Option 2, Option 3" />
                        </div>
                      )}
                      <div className="flex items-center space-x-2">
                        <input type="checkbox" id="required" checked={fieldRequired} onChange={(e) => setFieldRequired(e.target.checked)} />
                        <Label htmlFor="required">Required field</Label>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowFieldDialog(false)}>Cancel</Button>
                      <Button onClick={handleSaveCustomField}>Save</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Required</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {customFields.map((field) => (
                      <TableRow key={field.id}>
                        <TableCell className="font-medium">{field.name}</TableCell>
                        <TableCell>{field.field_type}</TableCell>
                        <TableCell>{field.is_required ? 'Yes' : 'No'}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditingField(field);
                              setFieldName(field.name);
                              setFieldType(field.field_type);
                              setFieldRequired(field.is_required);
                              setFieldOptions(field.options?.join(', ') || '');
                              setShowFieldDialog(true);
                            }}
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDeleteCustomField(field.id)}>
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="fees">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Fees</CardTitle>
                  <CardDescription>Configure fees for late changes, expedite requests, etc.</CardDescription>
                </div>
                <Dialog open={showFeeDialog} onOpenChange={setShowFeeDialog}>
                  <DialogTrigger asChild>
                    <Button onClick={() => { setEditingFee(null); setFeeName(''); setFeeType(''); setFeeAmount(''); setFeeDescription(''); }}>
                      <Plus className="w-4 h-4 mr-2" />
                      Add Fee
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>{editingFee ? 'Edit Fee' : 'Add Fee'}</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label>Fee Name</Label>
                        <Input value={feeName} onChange={(e) => setFeeName(e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Fee Type</Label>
                        <Select value={feeType} onValueChange={setFeeType}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="late_change">Late Change</SelectItem>
                            <SelectItem value="cancellation">Cancellation</SelectItem>
                            <SelectItem value="expedite">Expedite</SelectItem>
                            <SelectItem value="other">Other</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Amount (£)</Label>
                        <Input type="number" step="0.01" value={feeAmount} onChange={(e) => setFeeAmount(e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Description</Label>
                        <Textarea value={feeDescription} onChange={(e) => setFeeDescription(e.target.value)} />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowFeeDialog(false)}>Cancel</Button>
                      <Button onClick={handleSaveFee}>Save</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {fees.map((fee) => (
                      <TableRow key={fee.id}>
                        <TableCell className="font-medium">{fee.name}</TableCell>
                        <TableCell>{fee.fee_type}</TableCell>
                        <TableCell>£{fee.amount.toFixed(2)}</TableCell>
                        <TableCell>{fee.description || '-'}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditingFee(fee);
                              setFeeName(fee.name);
                              setFeeType(fee.fee_type);
                              setFeeAmount(fee.amount.toString());
                              setFeeDescription(fee.description || '');
                              setShowFeeDialog(true);
                            }}
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDeleteFee(fee.id)}>
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="reports">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <BarChart3 className="w-5 h-5" />
                      MIS Reports
                    </CardTitle>
                    <CardDescription>Generate and export reports for bookings, engineers, products, and revenue</CardDescription>
                  </div>
                  <Button onClick={exportToExcel} disabled={reportData.length === 0 && reportType !== 'revenue'}>
                    <FileSpreadsheet className="w-4 h-4 mr-2" />
                    Export to Excel
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="space-y-2">
                    <Label>Report Type</Label>
                    <Select value={reportType} onValueChange={setReportType}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="bookings">Bookings Report</SelectItem>
                        <SelectItem value="engineers">Engineer Utilization</SelectItem>
                        <SelectItem value="products">Products Summary</SelectItem>
                        <SelectItem value="expedite">Expedite Requests</SelectItem>
                        <SelectItem value="revenue">Revenue Summary</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Start Date</Label>
                    <Input type="date" value={reportStartDate} onChange={(e) => setReportStartDate(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label>End Date</Label>
                    <Input type="date" value={reportEndDate} onChange={(e) => setReportEndDate(e.target.value)} />
                  </div>
                  <div className="space-y-2 flex items-end">
                    <Button onClick={loadReport} disabled={isLoadingReport} className="w-full">
                      {isLoadingReport ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                      Generate Report
                    </Button>
                  </div>
                </div>

                {reportType === 'bookings' && (
                  <div className="grid grid-cols-3 gap-4 p-4 bg-gray-50 rounded-lg">
                    <div className="space-y-2">
                      <Label>Product Filter</Label>
                      <Select value={reportProductFilter} onValueChange={setReportProductFilter}>
                        <SelectTrigger>
                          <SelectValue placeholder="All Products" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Products</SelectItem>
                          {products.map(p => (
                            <SelectItem key={p.id} value={p.id.toString()}>{p.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Engineer Filter</Label>
                      <Select value={reportEngineerFilter} onValueChange={setReportEngineerFilter}>
                        <SelectTrigger>
                          <SelectValue placeholder="All Engineers" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Engineers</SelectItem>
                          {engineers.map(e => (
                            <SelectItem key={e.id} value={e.id.toString()}>{e.user?.full_name || e.calendar_email}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Status Filter</Label>
                      <Select value={reportStatusFilter} onValueChange={setReportStatusFilter}>
                        <SelectTrigger>
                          <SelectValue placeholder="All Statuses" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Statuses</SelectItem>
                          <SelectItem value="pending">Pending</SelectItem>
                          <SelectItem value="confirmed">Confirmed</SelectItem>
                          <SelectItem value="completed">Completed</SelectItem>
                          <SelectItem value="cancelled">Cancelled</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                )}

                {reportType === 'revenue' && revenueSummary && (
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold">{revenueSummary.total_bookings}</div>
                        <p className="text-sm text-gray-500">Total Bookings</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-green-600">${revenueSummary.total_expedite_fees?.toFixed(2) || '0.00'}</div>
                        <p className="text-sm text-gray-500">Expedite Fees</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-red-600">${revenueSummary.total_cancellation_fees?.toFixed(2) || '0.00'}</div>
                        <p className="text-sm text-gray-500">Cancellation Fees</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold">{revenueSummary.approved_expedite_requests}</div>
                        <p className="text-sm text-gray-500">Approved Expedite Requests</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-blue-600">${revenueSummary.expedite_request_fees?.toFixed(2) || '0.00'}</div>
                        <p className="text-sm text-gray-500">Expedite Request Fees</p>
                      </CardContent>
                    </Card>
                    {revenueSummary.status_breakdown && (
                      <Card>
                        <CardContent className="pt-6">
                          <div className="text-sm font-medium mb-2">Status Breakdown</div>
                          {Object.entries(revenueSummary.status_breakdown).map(([status, count]) => (
                            <div key={status} className="flex justify-between text-sm">
                              <span className="capitalize">{status}</span>
                              <span className="font-medium">{count as number}</span>
                            </div>
                          ))}
                        </CardContent>
                      </Card>
                    )}
                  </div>
                )}

                {reportType !== 'revenue' && reportData.length > 0 && (
                  <div className="border rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          {reportType === 'bookings' && (
                            <>
                              <TableHead>Order Ref</TableHead>
                              <TableHead>Customer</TableHead>
                              <TableHead>Date</TableHead>
                              <TableHead>Duration</TableHead>
                              <TableHead>Status</TableHead>
                              <TableHead>Product</TableHead>
                              <TableHead>Engineer</TableHead>
                              <TableHead>Fees</TableHead>
                            </>
                          )}
                          {reportType === 'engineers' && (
                            <>
                              <TableHead>Engineer</TableHead>
                              <TableHead>Email</TableHead>
                              <TableHead>Available</TableHead>
                              <TableHead>Total Bookings</TableHead>
                              <TableHead>Completed</TableHead>
                              <TableHead>Total Hours</TableHead>
                            </>
                          )}
                          {reportType === 'products' && (
                            <>
                              <TableHead>Product</TableHead>
                              <TableHead>Total Bookings</TableHead>
                              <TableHead>Total Hours</TableHead>
                              <TableHead>Expedite Fees</TableHead>
                              <TableHead>Cancellation Fees</TableHead>
                            </>
                          )}
                          {reportType === 'expedite' && (
                            <>
                              <TableHead>Order Ref</TableHead>
                              <TableHead>Customer</TableHead>
                              <TableHead>Requested Date</TableHead>
                              <TableHead>Status</TableHead>
                              <TableHead>Product</TableHead>
                              <TableHead>Fee</TableHead>
                              <TableHead>Assigned Engineer</TableHead>
                            </>
                          )}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {reportType === 'bookings' && reportData.map((b: any) => (
                          <TableRow key={b.id}>
                            <TableCell className="font-medium">{b.order_reference}</TableCell>
                            <TableCell>{b.customer_name}</TableCell>
                            <TableCell>{b.scheduled_date ? new Date(b.scheduled_date).toLocaleDateString() : '-'}</TableCell>
                            <TableCell>{b.duration_hours}h</TableCell>
                            <TableCell>
                              <Badge variant="outline" className={
                                b.status === 'confirmed' ? 'bg-green-100 text-green-800' :
                                b.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                                b.status === 'completed' ? 'bg-blue-100 text-blue-800' :
                                'bg-red-100 text-red-800'
                              }>{b.status}</Badge>
                            </TableCell>
                            <TableCell>{b.product_name}</TableCell>
                            <TableCell>{b.engineer_name}</TableCell>
                            <TableCell>${((b.expedite_fee || 0) + (b.cancellation_fee || 0)).toFixed(2)}</TableCell>
                          </TableRow>
                        ))}
                        {reportType === 'engineers' && reportData.map((e: any) => (
                          <TableRow key={e.engineer_id}>
                            <TableCell className="font-medium">{e.engineer_name}</TableCell>
                            <TableCell>{e.calendar_email}</TableCell>
                            <TableCell>
                              <Badge variant="outline" className={e.is_available ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                                {e.is_available ? 'Yes' : 'No'}
                              </Badge>
                            </TableCell>
                            <TableCell>{e.total_bookings}</TableCell>
                            <TableCell>{e.completed_bookings}</TableCell>
                            <TableCell>{e.total_hours}h</TableCell>
                          </TableRow>
                        ))}
                        {reportType === 'products' && reportData.map((p: any) => (
                          <TableRow key={p.product_id}>
                            <TableCell className="font-medium">{p.product_name}</TableCell>
                            <TableCell>{p.total_bookings}</TableCell>
                            <TableCell>{p.total_hours}h</TableCell>
                            <TableCell>${p.total_expedite_fees?.toFixed(2) || '0.00'}</TableCell>
                            <TableCell>${p.total_cancellation_fees?.toFixed(2) || '0.00'}</TableCell>
                          </TableRow>
                        ))}
                        {reportType === 'expedite' && reportData.map((r: any) => (
                          <TableRow key={r.id}>
                            <TableCell className="font-medium">{r.order_reference}</TableCell>
                            <TableCell>{r.customer_name}</TableCell>
                            <TableCell>{r.requested_date ? new Date(r.requested_date).toLocaleDateString() : '-'}</TableCell>
                            <TableCell>
                              <Badge variant="outline" className={getStatusBadgeColor(r.status)}>{r.status}</Badge>
                            </TableCell>
                            <TableCell>{r.product_name}</TableCell>
                            <TableCell>${r.expedite_fee?.toFixed(2) || '0.00'}</TableCell>
                            <TableCell>{r.assigned_engineer_name || '-'}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}

                {reportType !== 'revenue' && reportData.length === 0 && !isLoadingReport && (
                  <div className="text-center py-12 text-gray-500">
                    <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>Select a report type and date range, then click "Generate Report" to view data</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="email-templates">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Email Templates</CardTitle>
                  <CardDescription>Create email templates with booking field placeholders for confirmations, amendments, cancellations, and reminders</CardDescription>
                </div>
                <Dialog open={showEmailTemplateDialog} onOpenChange={setShowEmailTemplateDialog}>
                  <DialogTrigger asChild>
                    <Button onClick={resetEmailTemplateForm}>
                      <Plus className="w-4 h-4 mr-2" />
                      Add Email Template
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                      <DialogTitle>{editingEmailTemplate ? 'Edit Email Template' : 'Create Email Template'}</DialogTitle>
                      <DialogDescription>
                        Use placeholders like {"{{customer_name}}"} to insert booking data into your template
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label>Template Name</Label>
                          <Input 
                            value={emailTemplateName}
                            onChange={(e) => setEmailTemplateName(e.target.value)}
                            placeholder="e.g., Booking Confirmation"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Template Type</Label>
                          <Select value={emailTemplateType} onValueChange={(v) => setEmailTemplateType(v as TemplateType)}>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="confirmation">Confirmation</SelectItem>
                              <SelectItem value="amendment">Amendment</SelectItem>
                              <SelectItem value="cancellation">Cancellation</SelectItem>
                              <SelectItem value="reminder">Reminder</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      
                      <div className="space-y-2">
                        <Label>Email Subject</Label>
                        <Input 
                          ref={emailSubjectRef}
                          value={emailTemplateSubject} 
                          onChange={(e) => setEmailTemplateSubject(e.target.value)}
                          onFocus={() => setActiveField('emailSubject')}
                          placeholder="e.g., Booking Confirmation - {{order_reference}}"
                          className={activeField === 'emailSubject' ? 'ring-2 ring-indigo-500' : ''}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>Email Body (HTML)</Label>
                        <Textarea 
                          ref={emailBodyRef}
                          value={emailTemplateBody} 
                          onChange={(e) => setEmailTemplateBody(e.target.value)}
                          onFocus={() => setActiveField('emailBody')}
                          placeholder="<p>Dear {{customer_name}},</p><p>Your booking has been confirmed...</p>"
                          className={`min-h-48 font-mono text-sm ${activeField === 'emailBody' ? 'ring-2 ring-indigo-500' : ''}`}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>Data Field Selector</Label>
                        <p className="text-xs text-gray-500 mb-2">Click on a field above, then click a placeholder below to insert it at your cursor position</p>
                        <div className="flex flex-wrap gap-1 p-3 bg-gray-50 rounded-lg border">
                          {templatePlaceholders.map((placeholder) => (
                            <Button
                              key={placeholder}
                              variant={activeField ? 'default' : 'outline'}
                              size="sm"
                              className="text-xs h-7"
                              onClick={() => insertPlaceholderAtCursor(placeholder)}
                              disabled={!activeField}
                            >
                              {placeholder}
                            </Button>
                          ))}
                        </div>
                        {!activeField && (
                          <p className="text-xs text-amber-600 mt-1">Click on the Subject or Body field first to enable placeholder insertion</p>
                        )}
                      </div>

                      <div className="border-t pt-4">
                        <Label className="text-base font-medium">Company Branding</Label>
                        <div className="mt-3 space-y-3">
                          <div className="space-y-2">
                            <Label>Company Logo</Label>
                            <div className="flex gap-2">
                              <Input 
                                value={emailTemplateLogoUrl} 
                                onChange={(e) => setEmailTemplateLogoUrl(e.target.value)}
                                placeholder="https://example.com/logo.png"
                                className="flex-1"
                              />
                              <div className="relative">
                                <input
                                  type="file"
                                  accept="image/*"
                                  onChange={handleLogoUpload}
                                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                  disabled={isUploadingLogo}
                                />
                                <Button variant="outline" disabled={isUploadingLogo}>
                                  {isUploadingLogo ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                  ) : (
                                    <Upload className="w-4 h-4" />
                                  )}
                                </Button>
                              </div>
                            </div>
                            <p className="text-xs text-gray-500">Enter a URL or upload an image file. This will be displayed at the top of the email.</p>
                          </div>
                          {emailTemplateLogoUrl && (
                            <div className="p-3 bg-gray-50 rounded-lg border">
                              <p className="text-xs text-gray-500 mb-2">Logo Preview:</p>
                              <img 
                                src={emailTemplateLogoUrl} 
                                alt="Company Logo Preview" 
                                className="max-h-16 max-w-48 object-contain"
                                onError={(e) => {
                                  (e.target as HTMLImageElement).style.display = 'none';
                                }}
                              />
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="border-t pt-4">
                        <Label className="text-base font-medium">Recipients</Label>
                        <div className="mt-3 space-y-3">
                          <div className="flex items-center space-x-2">
                            <Checkbox 
                              id="sendToEngineer"
                              checked={emailTemplateSendToEngineer}
                              onCheckedChange={(checked) => setEmailTemplateSendToEngineer(checked as boolean)}
                            />
                            <label htmlFor="sendToEngineer" className="text-sm">Send to Engineer</label>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Checkbox 
                              id="sendToCustomer"
                              checked={emailTemplateSendToCustomer}
                              onCheckedChange={(checked) => setEmailTemplateSendToCustomer(checked as boolean)}
                            />
                            <label htmlFor="sendToCustomer" className="text-sm">Send to Customer (Booker)</label>
                          </div>
                          <div className="space-y-2">
                            <Label>Additional Email Addresses (comma-separated)</Label>
                            <Input 
                              value={emailTemplateAdditionalEmails} 
                              onChange={(e) => setEmailTemplateAdditionalEmails(e.target.value)}
                              placeholder="manager@company.com, support@company.com"
                            />
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        <Checkbox 
                          id="isDefault"
                          checked={emailTemplateIsDefault}
                          onCheckedChange={(checked) => setEmailTemplateIsDefault(checked as boolean)}
                        />
                        <label htmlFor="isDefault" className="text-sm">Set as default template for this type</label>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowEmailTemplateDialog(false)}>Cancel</Button>
                      <Button onClick={handleSaveEmailTemplate}>Save Template</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </CardHeader>
              <CardContent>
                {emailTemplates.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <Mail className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                    <p>No email templates created yet</p>
                    <p className="text-sm">Create templates to customize booking notifications</p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Subject</TableHead>
                        <TableHead>Recipients</TableHead>
                        <TableHead>Default</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {emailTemplates.map((template) => (
                        <TableRow key={template.id}>
                          <TableCell className="font-medium">{template.name}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className="capitalize">{template.template_type}</Badge>
                          </TableCell>
                          <TableCell className="max-w-xs truncate">{template.subject}</TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              {template.send_to_engineer && <Badge variant="secondary" className="text-xs">Engineer</Badge>}
                              {template.send_to_customer && <Badge variant="secondary" className="text-xs">Customer</Badge>}
                              {template.additional_emails && template.additional_emails.length > 0 && (
                                <Badge variant="secondary" className="text-xs">+{template.additional_emails.length}</Badge>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            {template.is_default && <Badge className="bg-green-100 text-green-800">Default</Badge>}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" size="sm" onClick={() => openEditEmailTemplate(template)}>
                              <Edit className="w-4 h-4" />
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => handleDeleteEmailTemplate(template.id)}>
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="calendar-templates">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Calendar Event Templates</CardTitle>
                  <CardDescription>Create Outlook calendar event templates for booking notifications</CardDescription>
                </div>
                <Dialog open={showCalendarTemplateDialog} onOpenChange={setShowCalendarTemplateDialog}>
                  <DialogTrigger asChild>
                    <Button onClick={resetCalendarTemplateForm}>
                      <Plus className="w-4 h-4 mr-2" />
                      Add Calendar Template
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                      <DialogTitle>{editingCalendarTemplate ? 'Edit Calendar Template' : 'Create Calendar Template'}</DialogTitle>
                      <DialogDescription>
                        Use placeholders like {"{{customer_name}}"} to insert booking data into calendar events
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label>Template Name</Label>
                          <Input 
                            value={calendarTemplateName} 
                            onChange={(e) => setCalendarTemplateName(e.target.value)}
                            placeholder="e.g., Engineer Booking Event"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Template Type</Label>
                          <Select value={calendarTemplateType} onValueChange={(v) => setCalendarTemplateType(v as TemplateType)}>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="confirmation">Confirmation</SelectItem>
                              <SelectItem value="amendment">Amendment</SelectItem>
                              <SelectItem value="cancellation">Cancellation</SelectItem>
                              <SelectItem value="reminder">Reminder</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      
                      <div className="space-y-2">
                        <Label>Event Title</Label>
                        <Input 
                          ref={calendarTitleRef}
                          value={calendarTemplateTitle} 
                          onChange={(e) => setCalendarTemplateTitle(e.target.value)}
                          onFocus={() => setActiveField('calendarTitle')}
                          placeholder="e.g., {{product_name}} - {{customer_name}} ({{order_reference}})"
                          className={activeField === 'calendarTitle' ? 'ring-2 ring-indigo-500' : ''}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>Event Description</Label>
                        <Textarea 
                          ref={calendarBodyRef}
                          value={calendarTemplateBody} 
                          onChange={(e) => setCalendarTemplateBody(e.target.value)}
                          onFocus={() => setActiveField('calendarBody')}
                          placeholder="Order: {{order_reference}}&#10;Customer: {{customer_name}}&#10;Product: {{product_name}}&#10;Change Type: {{change_type}}"
                          className={`min-h-32 ${activeField === 'calendarBody' ? 'ring-2 ring-indigo-500' : ''}`}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>Data Field Selector</Label>
                        <p className="text-xs text-gray-500 mb-2">Click on Event Title or Description above, then click a placeholder below to insert it at your cursor position</p>
                        <div className="flex flex-wrap gap-1 p-3 bg-gray-50 rounded-lg border">
                          {templatePlaceholders.map((placeholder) => (
                            <Button
                              key={placeholder}
                              variant={(activeField === 'calendarTitle' || activeField === 'calendarBody') ? 'default' : 'outline'}
                              size="sm"
                              className="text-xs h-7"
                              onClick={() => insertPlaceholderAtCursor(placeholder)}
                              disabled={activeField !== 'calendarTitle' && activeField !== 'calendarBody'}
                            >
                              {placeholder}
                            </Button>
                          ))}
                        </div>
                        {activeField !== 'calendarTitle' && activeField !== 'calendarBody' && (
                          <p className="text-xs text-amber-600 mt-1">Click on the Event Title or Description field first to enable placeholder insertion</p>
                        )}
                      </div>

                      <div className="border-t pt-4">
                        <Label className="text-base font-medium">Attendees</Label>
                        <div className="mt-3 space-y-3">
                          <div className="flex items-center space-x-2">
                            <Checkbox 
                              id="includeCustomer"
                              checked={calendarTemplateIncludeCustomer}
                              onCheckedChange={(checked) => setCalendarTemplateIncludeCustomer(checked as boolean)}
                            />
                            <label htmlFor="includeCustomer" className="text-sm">Include Customer (Booker) as Attendee</label>
                          </div>
                          <div className="space-y-2">
                            <Label>Additional Attendees (comma-separated emails)</Label>
                            <Input 
                              value={calendarTemplateAdditionalAttendees} 
                              onChange={(e) => setCalendarTemplateAdditionalAttendees(e.target.value)}
                              placeholder="manager@company.com, support@company.com"
                            />
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        <Checkbox 
                          id="calIsDefault"
                          checked={calendarTemplateIsDefault}
                          onCheckedChange={(checked) => setCalendarTemplateIsDefault(checked as boolean)}
                        />
                        <label htmlFor="calIsDefault" className="text-sm">Set as default template for this type</label>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowCalendarTemplateDialog(false)}>Cancel</Button>
                      <Button onClick={handleSaveCalendarTemplate}>Save Template</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </CardHeader>
              <CardContent>
                {calendarTemplates.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <CalendarDays className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                    <p>No calendar templates created yet</p>
                    <p className="text-sm">Create templates to customize Outlook calendar events</p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Event Title</TableHead>
                        <TableHead>Attendees</TableHead>
                        <TableHead>Default</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {calendarTemplates.map((template) => (
                        <TableRow key={template.id}>
                          <TableCell className="font-medium">{template.name}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className="capitalize">{template.template_type}</Badge>
                          </TableCell>
                          <TableCell className="max-w-xs truncate">{template.event_title}</TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              {template.include_customer_as_attendee && <Badge variant="secondary" className="text-xs">Customer</Badge>}
                              {template.additional_attendees && template.additional_attendees.length > 0 && (
                                <Badge variant="secondary" className="text-xs">+{template.additional_attendees.length}</Badge>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            {template.is_default && <Badge className="bg-green-100 text-green-800">Default</Badge>}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" size="sm" onClick={() => openEditCalendarTemplate(template)}>
                              <Edit className="w-4 h-4" />
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => handleDeleteCalendarTemplate(template.id)}>
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="expedite-requests">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Expedite Requests</CardTitle>
                  <CardDescription>Manage expedite requests from users when no availability exists</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Label className="text-sm">Filter:</Label>
                  <Select value={expediteStatusFilter} onValueChange={setExpediteStatusFilter}>
                    <SelectTrigger className="w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="pending">Pending</SelectItem>
                      <SelectItem value="approved">Approved</SelectItem>
                      <SelectItem value="rejected">Rejected</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent>
                {expediteRequests.length === 0 ? (
                  <p className="text-center text-gray-500 py-8">No expedite requests found</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Order Ref</TableHead>
                        <TableHead>Customer</TableHead>
                        <TableHead>Product</TableHead>
                        <TableHead>Requested Date</TableHead>
                        <TableHead>Duration</TableHead>
                        <TableHead>Fee</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Submitted</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {expediteRequests.map((request) => (
                        <TableRow key={request.id}>
                          <TableCell className="font-medium">{request.order_reference}</TableCell>
                          <TableCell>{request.customer_name}</TableCell>
                          <TableCell>{request.product?.name || '-'}</TableCell>
                          <TableCell>{new Date(request.requested_date).toLocaleDateString()}</TableCell>
                          <TableCell>{request.duration_hours}h</TableCell>
                          <TableCell>${request.expedite_fee.toFixed(2)}</TableCell>
                          <TableCell>
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusBadgeColor(request.status)}`}>
                              {request.status}
                            </span>
                          </TableCell>
                          <TableCell>{new Date(request.created_at).toLocaleDateString()}</TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setSelectedExpediteRequest(request);
                                setShowExpediteDetailDialog(true);
                              }}
                            >
                              View
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            {/* Expedite Request Detail Dialog */}
            <Dialog open={showExpediteDetailDialog} onOpenChange={setShowExpediteDetailDialog}>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Expedite Request Details</DialogTitle>
                </DialogHeader>
                {selectedExpediteRequest && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label className="text-sm text-gray-500">Order Reference</Label>
                        <p className="font-medium">{selectedExpediteRequest.order_reference}</p>
                      </div>
                      <div>
                        <Label className="text-sm text-gray-500">Customer Name</Label>
                        <p className="font-medium">{selectedExpediteRequest.customer_name}</p>
                      </div>
                      <div>
                        <Label className="text-sm text-gray-500">Product</Label>
                        <p className="font-medium">{selectedExpediteRequest.product?.name || '-'}</p>
                      </div>
                      <div>
                        <Label className="text-sm text-gray-500">Change Type</Label>
                        <p className="font-medium">{selectedExpediteRequest.change_type?.name || '-'}</p>
                      </div>
                      <div>
                        <Label className="text-sm text-gray-500">Requested Date</Label>
                        <p className="font-medium">{new Date(selectedExpediteRequest.requested_date).toLocaleString()}</p>
                      </div>
                      <div>
                        <Label className="text-sm text-gray-500">Duration</Label>
                        <p className="font-medium">{selectedExpediteRequest.duration_hours} hours</p>
                      </div>
                      <div>
                        <Label className="text-sm text-gray-500">Expedite Fee</Label>
                        <p className="font-medium">${selectedExpediteRequest.expedite_fee.toFixed(2)}</p>
                      </div>
                      <div>
                        <Label className="text-sm text-gray-500">Status</Label>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusBadgeColor(selectedExpediteRequest.status)}`}>
                          {selectedExpediteRequest.status}
                        </span>
                      </div>
                      <div>
                        <Label className="text-sm text-gray-500">Requester</Label>
                        <p className="font-medium">{selectedExpediteRequest.requester?.full_name || '-'}</p>
                      </div>
                      <div>
                        <Label className="text-sm text-gray-500">Submitted</Label>
                        <p className="font-medium">{new Date(selectedExpediteRequest.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                    {selectedExpediteRequest.notes && (
                      <div>
                        <Label className="text-sm text-gray-500">Notes</Label>
                        <p className="mt-1 p-2 bg-gray-50 rounded">{selectedExpediteRequest.notes}</p>
                      </div>
                    )}
                    {selectedExpediteRequest.additional_emails && selectedExpediteRequest.additional_emails.length > 0 && (
                      <div>
                        <Label className="text-sm text-gray-500">Additional Email Recipients</Label>
                        <p className="font-medium">{selectedExpediteRequest.additional_emails.join(', ')}</p>
                      </div>
                    )}
                    {selectedExpediteRequest.admin_notes && (
                      <div>
                        <Label className="text-sm text-gray-500">Admin Notes</Label>
                        <p className="mt-1 p-2 bg-gray-50 rounded">{selectedExpediteRequest.admin_notes}</p>
                      </div>
                    )}
                    {selectedExpediteRequest.assigned_engineer && (
                      <div>
                        <Label className="text-sm text-gray-500">Assigned Engineer</Label>
                        <p className="font-medium">{selectedExpediteRequest.assigned_engineer.user?.full_name || '-'}</p>
                      </div>
                    )}
                  </div>
                )}
                <DialogFooter>
                  {selectedExpediteRequest?.status === 'pending' && (
                    <>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setShowRejectDialog(true);
                        }}
                      >
                        Reject
                      </Button>
                      <Button
                        onClick={() => {
                          setApproveScheduledDate(selectedExpediteRequest.requested_date.slice(0, 16));
                          setShowApproveDialog(true);
                        }}
                      >
                        Approve
                      </Button>
                    </>
                  )}
                  <Button variant="ghost" onClick={() => setShowExpediteDetailDialog(false)}>
                    Close
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* Approve Dialog */}
            <Dialog open={showApproveDialog} onOpenChange={setShowApproveDialog}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Approve Expedite Request</DialogTitle>
                  <DialogDescription>
                    Assign an engineer and confirm the scheduled date/time for this expedite request.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Assign Engineer</Label>
                    <Select
                      value={approveEngineerId?.toString() || ''}
                      onValueChange={(val) => setApproveEngineerId(parseInt(val))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select an engineer" />
                      </SelectTrigger>
                      <SelectContent>
                        {engineers.map((eng) => (
                          <SelectItem key={eng.id} value={eng.id.toString()}>
                            {eng.user?.full_name || eng.calendar_email}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Scheduled Date & Time</Label>
                    <Input
                      type="datetime-local"
                      value={approveScheduledDate}
                      onChange={(e) => setApproveScheduledDate(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Admin Notes (optional)</Label>
                    <Textarea
                      value={approveAdminNotes}
                      onChange={(e) => setApproveAdminNotes(e.target.value)}
                      placeholder="Add any notes about this approval..."
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setShowApproveDialog(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={handleApproveExpediteRequest}
                    disabled={!approveEngineerId || !approveScheduledDate || isProcessingExpedite}
                  >
                    {isProcessingExpedite ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      'Approve & Create Booking'
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* Reject Dialog */}
            <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Reject Expedite Request</DialogTitle>
                  <DialogDescription>
                    Provide a reason for rejecting this expedite request.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Rejection Reason (optional)</Label>
                    <Textarea
                      value={rejectAdminNotes}
                      onChange={(e) => setRejectAdminNotes(e.target.value)}
                      placeholder="Explain why this request is being rejected..."
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setShowRejectDialog(false)}>
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={handleRejectExpediteRequest}
                    disabled={isProcessingExpedite}
                  >
                    {isProcessingExpedite ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      'Reject Request'
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </TabsContent>

          <TabsContent value="config">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>System Settings</CardTitle>
                  <CardDescription>Configure system-wide settings like deadlines</CardDescription>
                </div>
                <Dialog open={showConfigDialog} onOpenChange={setShowConfigDialog}>
                  <DialogTrigger asChild>
                    <Button>
                      <Plus className="w-4 h-4 mr-2" />
                      Add Setting
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Add System Setting</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label>Key</Label>
                        <Select value={configKey} onValueChange={setConfigKey}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select setting" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="amendment_deadline_hours">Amendment Deadline (hours)</SelectItem>
                            <SelectItem value="cancellation_deadline_hours">Cancellation Deadline (hours)</SelectItem>
                            <SelectItem value="min_booking_notice_hours">Minimum Booking Notice (hours)</SelectItem>
                            <SelectItem value="max_booking_duration_hours">Maximum Booking Duration (hours)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Value</Label>
                        <Input value={configValue} onChange={(e) => setConfigValue(e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Description</Label>
                        <Textarea value={configDescription} onChange={(e) => setConfigDescription(e.target.value)} />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowConfigDialog(false)}>Cancel</Button>
                      <Button onClick={handleSaveConfig}>Save</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Setting</TableHead>
                      <TableHead>Value</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Last Updated</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {configs.map((config) => (
                      <TableRow key={config.id}>
                        <TableCell className="font-medium">{config.key}</TableCell>
                        <TableCell>{config.value}</TableCell>
                        <TableCell>{config.description || '-'}</TableCell>
                        <TableCell>{new Date(config.updated_at).toLocaleDateString()}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            <Card className="mt-6">
              <CardHeader>
                <CardTitle>Microsoft / SharePoint Integration</CardTitle>
                <CardDescription>
                  Configure SharePoint site and list for booking data storage, and Microsoft Azure AD for calendar integration
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Microsoft Client ID (Azure AD)</Label>
                      <Input 
                        value={microsoftClientId} 
                        onChange={(e) => setMicrosoftClientId(e.target.value)}
                        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                      />
                      <p className="text-xs text-gray-500">From Azure AD App Registration</p>
                    </div>
                    <div className="space-y-2">
                      <Label>Microsoft Tenant ID</Label>
                      <Input 
                        value={microsoftTenantId} 
                        onChange={(e) => setMicrosoftTenantId(e.target.value)}
                        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                      />
                      <p className="text-xs text-gray-500">Your Microsoft 365 tenant ID</p>
                    </div>
                  </div>

                  <div className="border-t pt-4">
                    <h4 className="font-medium mb-3">SharePoint Configuration</h4>
                    <div className="grid gap-4 md:grid-cols-1">
                      <div className="space-y-2">
                        <Label>SharePoint Site URL</Label>
                        <Input 
                          value={sharepointSiteUrl} 
                          onChange={(e) => setSharepointSiteUrl(e.target.value)}
                          placeholder="https://yourcompany.sharepoint.com/sites/YourSite"
                        />
                        <p className="text-xs text-gray-500">The full URL of your SharePoint site</p>
                      </div>
                      <div className="space-y-2">
                        <Label>SharePoint Site ID</Label>
                        <Input 
                          value={sharepointSiteId} 
                          onChange={(e) => setSharepointSiteId(e.target.value)}
                          placeholder="yourcompany.sharepoint.com,guid,guid"
                        />
                        <p className="text-xs text-gray-500">Site ID from Microsoft Graph API</p>
                      </div>
                      <div className="space-y-2">
                        <Label>SharePoint List ID (for Bookings)</Label>
                        <Input 
                          value={sharepointListId} 
                          onChange={(e) => setSharepointListId(e.target.value)}
                          placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                        />
                        <p className="text-xs text-gray-500">The ID of the SharePoint list where bookings will be stored</p>
                      </div>
                    </div>
                  </div>

                  {sharepointStatus && (
                    <div className={`p-3 rounded-lg ${sharepointStatus.includes('success') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                      {sharepointStatus}
                    </div>
                  )}

                  <div className="flex justify-end">
                    <Button onClick={handleSaveSharepointConfig} disabled={isSavingSharepoint}>
                      {isSavingSharepoint ? 'Saving...' : 'Save Integration Settings'}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="mt-6">
              <CardHeader>
                <CardTitle>User Management</CardTitle>
                <CardDescription>Manage user roles</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((u) => (
                      <TableRow key={u.id}>
                        <TableCell className="font-medium">{u.full_name}</TableCell>
                        <TableCell>{u.email}</TableCell>
                        <TableCell>
                          <Badge>{u.role}</Badge>
                        </TableCell>
                        <TableCell>{new Date(u.created_at).toLocaleDateString()}</TableCell>
                        <TableCell className="text-right">
                          <Select
                            value={u.role}
                            onValueChange={(role) => handleUpdateUserRole(u.id, role)}
                            disabled={u.id === user?.id}
                          >
                            <SelectTrigger className="w-32">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="user">User</SelectItem>
                              <SelectItem value="engineer">Engineer</SelectItem>
                              <SelectItem value="admin">Admin</SelectItem>
                            </SelectContent>
                          </Select>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
