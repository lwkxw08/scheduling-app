import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import { Booking, Product, Engineer } from '../types';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Calendar, Plus, Settings, LogOut, Clock, User, FileText, Shield, Wrench, Search, X } from 'lucide-react';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user, logout, setAuthFromToken } = useAuth();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [engineers, setEngineers] = useState<Engineer[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAdminSetup, setShowAdminSetup] = useState(false);
  const [isPromoting, setIsPromoting] = useState(false);

  // App branding state
  const [appName, setAppName] = useState('Scheduling App');
  const [appLogoUrl, setAppLogoUrl] = useState('');

  // Search and filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [productFilter, setProductFilter] = useState<string>('all');
  const [engineerFilter, setEngineerFilter] = useState<string>('all');
  const [dateFromFilter, setDateFromFilter] = useState('');
  const [dateToFilter, setDateToFilter] = useState('');

  useEffect(() => {
    loadBookings();
    loadFiltersData();
    checkAdminSetup();
    loadBranding();
  }, []);

  const loadBranding = async () => {
    try {
      const configs = await api.getSystemConfig() as any[];
      const appNameConfig = configs.find((c: any) => c.key === 'app_name');
      const appLogoConfig = configs.find((c: any) => c.key === 'app_logo_url');
      if (appNameConfig) setAppName(appNameConfig.value);
      if (appLogoConfig) setAppLogoUrl(appLogoConfig.value);
    } catch (error) {
      console.error('Failed to load branding:', error);
    }
  };

  const checkAdminSetup = async () => {
    try {
      const status = await api.getSetupStatus();
      if (!status.has_admin && user?.role !== 'admin') {
        setShowAdminSetup(true);
      }
    } catch (error) {
      console.error('Failed to check admin setup:', error);
    }
  };

  const handlePromoteToAdmin = async () => {
    setIsPromoting(true);
    try {
      const response = await api.promoteToAdmin() as { access_token: string; token_type: string; user: any };
      setAuthFromToken(response);
      setShowAdminSetup(false);
      window.location.reload();
    } catch (error) {
      console.error('Failed to promote to admin:', error);
      alert('Failed to become admin. An admin may already exist.');
    } finally {
      setIsPromoting(false);
    }
  };

    const loadBookings = async () => {
      try {
        const data = await api.getBookings() as Booking[];
        setBookings(data);
      } catch (error) {
        console.error('Failed to load bookings:', error);
      } finally {
        setIsLoading(false);
      }
    };

    const loadFiltersData = async () => {
      try {
        const [productsData, engineersData] = await Promise.all([
          api.getProducts(),
          api.getEngineers(),
        ]);
        setProducts(productsData as Product[]);
        setEngineers(engineersData as Engineer[]);
      } catch (error) {
        console.error('Failed to load filter data:', error);
      }
    };

    const clearFilters = () => {
      setSearchQuery('');
      setStatusFilter('all');
      setProductFilter('all');
      setEngineerFilter('all');
      setDateFromFilter('');
      setDateToFilter('');
    };

    const hasActiveFilters = searchQuery || statusFilter !== 'all' || productFilter !== 'all' || engineerFilter !== 'all' || dateFromFilter || dateToFilter;

    // Filter bookings based on search and filters
    const filteredBookings = useMemo(() => {
      return bookings.filter(booking => {
        // Search filter
        if (searchQuery) {
          const query = searchQuery.toLowerCase();
          const matchesSearch = 
            booking.order_reference?.toLowerCase().includes(query) ||
            booking.customer_name?.toLowerCase().includes(query) ||
            booking.engineer?.user?.full_name?.toLowerCase().includes(query) ||
            booking.product?.name?.toLowerCase().includes(query);
          if (!matchesSearch) return false;
        }

        // Status filter
        if (statusFilter !== 'all' && booking.status !== statusFilter) {
          return false;
        }

        // Product filter
        if (productFilter !== 'all' && booking.product_id?.toString() !== productFilter) {
          return false;
        }

        // Engineer filter
        if (engineerFilter !== 'all' && booking.engineer_id?.toString() !== engineerFilter) {
          return false;
        }

        // Date range filter
        if (dateFromFilter) {
          const bookingDate = new Date(booking.scheduled_date);
          const fromDate = new Date(dateFromFilter);
          if (bookingDate < fromDate) return false;
        }

        if (dateToFilter) {
          const bookingDate = new Date(booking.scheduled_date);
          const toDate = new Date(dateToFilter);
          toDate.setHours(23, 59, 59, 999);
          if (bookingDate > toDate) return false;
        }

        return true;
      });
    }, [bookings, searchQuery, statusFilter, productFilter, engineerFilter, dateFromFilter, dateToFilter]);

  const handleLogout = () => {
    logout();
    navigate('/login');
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

    const upcomingBookings = filteredBookings
      .filter((b) => b.status !== 'cancelled' && new Date(b.scheduled_date) >= new Date())
      .sort((a, b) => new Date(a.scheduled_date).getTime() - new Date(b.scheduled_date).getTime());

    const pastBookings = filteredBookings
      .filter((b) => b.status === 'cancelled' || new Date(b.scheduled_date) < new Date())
      .sort((a, b) => new Date(b.scheduled_date).getTime() - new Date(a.scheduled_date).getTime());

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              {appLogoUrl ? (
                <img 
                  src={appLogoUrl} 
                  alt={appName} 
                  className="w-10 h-10 object-contain rounded-lg"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                    (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                  }}
                />
              ) : null}
              <div className={`w-10 h-10 bg-indigo-600 rounded-lg flex items-center justify-center ${appLogoUrl ? 'hidden' : ''}`}>
                <Calendar className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-gray-900">{appName}</h1>
                <p className="text-sm text-gray-500">Welcome, {user?.full_name}</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              {(user?.role === 'engineer' || user?.role === 'admin') && (
                <Button variant="outline" onClick={() => navigate('/engineer-dashboard')}>
                  <Wrench className="w-4 h-4 mr-2" />
                  Engineer Dashboard
                </Button>
              )}
              {user?.role === 'admin' && (
                <Button variant="outline" onClick={() => navigate('/admin')}>
                  <Settings className="w-4 h-4 mr-2" />
                  Admin
                </Button>
              )}
              <Button variant="ghost" onClick={handleLogout}>
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {showAdminSetup && (
          <Alert className="mb-6 border-indigo-200 bg-indigo-50">
            <Shield className="h-4 w-4 text-indigo-600" />
            <AlertDescription className="flex items-center justify-between">
              <span className="text-indigo-800">
                No admin has been set up yet. Would you like to become the admin?
              </span>
              <Button 
                size="sm" 
                onClick={handlePromoteToAdmin}
                disabled={isPromoting}
                className="ml-4"
              >
                {isPromoting ? 'Setting up...' : 'Become Admin'}
              </Button>
            </AlertDescription>
          </Alert>
        )}

        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Your Bookings</h2>
          <Button onClick={() => navigate('/book')}>
            <Plus className="w-4 h-4 mr-2" />
            New Booking
          </Button>
        </div>

        {/* Search and Filter Section */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="space-y-4">
              {/* Search Bar */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                <Input
                  placeholder="Search by order reference, customer name, engineer, or product..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>

              {/* Filter Row */}
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1 block">Status</label>
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
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

                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1 block">Product</label>
                  <Select value={productFilter} onValueChange={setProductFilter}>
                    <SelectTrigger>
                      <SelectValue placeholder="All Products" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Products</SelectItem>
                      {products.map((product) => (
                        <SelectItem key={product.id} value={product.id.toString()}>
                          {product.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1 block">Engineer</label>
                  <Select value={engineerFilter} onValueChange={setEngineerFilter}>
                    <SelectTrigger>
                      <SelectValue placeholder="All Engineers" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Engineers</SelectItem>
                      {engineers.map((engineer) => (
                        <SelectItem key={engineer.id} value={engineer.id.toString()}>
                          {engineer.user?.full_name || engineer.calendar_email}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1 block">From Date</label>
                  <Input
                    type="date"
                    value={dateFromFilter}
                    onChange={(e) => setDateFromFilter(e.target.value)}
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1 block">To Date</label>
                  <Input
                    type="date"
                    value={dateToFilter}
                    onChange={(e) => setDateToFilter(e.target.value)}
                  />
                </div>
              </div>

              {/* Clear Filters and Results Count */}
              <div className="flex justify-between items-center">
                <p className="text-sm text-gray-500">
                  Showing {filteredBookings.length} of {bookings.length} bookings
                </p>
                {hasActiveFilters && (
                  <Button variant="outline" size="sm" onClick={clearFilters}>
                    <X className="w-4 h-4 mr-1" />
                    Clear Filters
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {isLoading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
            <p className="mt-4 text-gray-500">Loading bookings...</p>
          </div>
        ) : bookings.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Calendar className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No bookings yet</h3>
              <p className="text-gray-500 mb-4">Create your first booking to get started</p>
              <Button onClick={() => navigate('/book')}>
                <Plus className="w-4 h-4 mr-2" />
                Create Booking
              </Button>
            </CardContent>
          </Card>
        ) : filteredBookings.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Search className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No bookings match your filters</h3>
              <p className="text-gray-500 mb-4">Try adjusting your search or filter criteria</p>
              <Button variant="outline" onClick={clearFilters}>
                <X className="w-4 h-4 mr-2" />
                Clear All Filters
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-8">
            {upcomingBookings.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Upcoming Bookings</h3>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {upcomingBookings.map((booking) => (
                    <Card key={booking.id} className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => navigate(`/booking/${booking.id}`)}>
                      <CardHeader className="pb-2">
                        <div className="flex justify-between items-start">
                          <CardTitle className="text-lg">{booking.order_reference}</CardTitle>
                          <Badge className={getStatusColor(booking.status)}>
                            {booking.status}
                          </Badge>
                        </div>
                        <CardDescription>{booking.customer_name}</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2 text-sm">
                          <div className="flex items-center text-gray-600">
                            <Calendar className="w-4 h-4 mr-2" />
                            {new Date(booking.scheduled_date).toLocaleDateString()}
                          </div>
                          <div className="flex items-center text-gray-600">
                            <Clock className="w-4 h-4 mr-2" />
                            {new Date(booking.scheduled_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} ({booking.duration_hours}h)
                          </div>
                          {booking.engineer?.user && (
                            <div className="flex items-center text-gray-600">
                              <User className="w-4 h-4 mr-2" />
                              {booking.engineer.user.full_name}
                            </div>
                          )}
                          {booking.product && (
                            <div className="flex items-center text-gray-600">
                              <FileText className="w-4 h-4 mr-2" />
                              {booking.product.name}
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}

            {pastBookings.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Past & Cancelled Bookings</h3>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {pastBookings.map((booking) => (
                    <Card key={booking.id} className="opacity-75 hover:opacity-100 transition-opacity cursor-pointer" onClick={() => navigate(`/booking/${booking.id}`)}>
                      <CardHeader className="pb-2">
                        <div className="flex justify-between items-start">
                          <CardTitle className="text-lg">{booking.order_reference}</CardTitle>
                          <Badge className={getStatusColor(booking.status)}>
                            {booking.status}
                          </Badge>
                        </div>
                        <CardDescription>{booking.customer_name}</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2 text-sm">
                          <div className="flex items-center text-gray-600">
                            <Calendar className="w-4 h-4 mr-2" />
                            {new Date(booking.scheduled_date).toLocaleDateString()}
                          </div>
                          <div className="flex items-center text-gray-600">
                            <Clock className="w-4 h-4 mr-2" />
                            {new Date(booking.scheduled_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} ({booking.duration_hours}h)
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
