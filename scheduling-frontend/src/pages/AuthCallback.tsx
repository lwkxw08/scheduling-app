import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import { TokenResponse } from '../types';
import { Spinner } from '../components/ui/spinner';

export default function AuthCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setAuthFromToken } = useAuth();
  const [error, setError] = useState('');

  useEffect(() => {
    const code = searchParams.get('code');
    
    if (code) {
      const redirectUri = `${window.location.origin}/auth/callback`;
      
      api.microsoftCallback(code, redirectUri)
        .then((response) => {
          setAuthFromToken(response as TokenResponse);
          navigate('/dashboard');
        })
        .catch((err) => {
          setError(err.message || 'Authentication failed');
        });
    } else {
      setError('No authorization code received');
    }
  }, [searchParams, navigate, setAuthFromToken]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-red-600 mb-2">Authentication Failed</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={() => navigate('/login')}
            className="text-indigo-600 hover:text-indigo-800"
          >
            Return to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <Spinner className="w-8 h-8 mx-auto mb-4" />
        <p className="text-gray-600">Completing authentication...</p>
      </div>
    </div>
  );
}
