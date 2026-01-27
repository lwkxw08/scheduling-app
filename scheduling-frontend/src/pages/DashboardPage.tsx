import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import { Booking } from '../types';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Calendar, Plus, Settings, LogOut, Clock, User, FileText, Shield, Wrench } from 'lucide-react';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user, logout, setAuthFromToken } = useAuth();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAdminSetup, setShowAdminSetup] = useState(false);
  const [isPromoting, setIsPromoting] = useState(false);

  useEffect(() => {
    loadBookings();
    checkAdminSetup();
  }, []);

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

  const upcomingBookings = bookings.filter(
    (b) => b.status !== 'cancelled' && new Date(b.scheduled_date) >= new Date()
  );

  const pastBookings = bookings.filter(
    (b) => b.status === 'cancelled' || new Date(b.scheduled_date) < new Date()
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-indigo-600 rounded-lg flex items-center justify-center">
                <Calendar className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-gray-900">Scheduling App</h1>
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
