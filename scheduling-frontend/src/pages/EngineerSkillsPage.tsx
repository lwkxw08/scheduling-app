import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import { Engineer, EngineerSkill, Product, ChangeType, RosterPatternListItem, EngineerRosterAssignment } from '../types';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { ArrowLeft, Plus, Trash2, User, Clock, Calendar, CalendarDays, Copy } from 'lucide-react';

interface EngineerSchedule {
  id?: number;
  engineer_id?: number;
  day_of_week: number;
  is_working: boolean;
  start_time: string;
  end_time: string;
}

const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

export default function EngineerSkillsPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  
  const [engineer, setEngineer] = useState<Engineer | null>(null);
  const [skills, setSkills] = useState<EngineerSkill[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [changeTypes, setChangeTypes] = useState<ChangeType[]>([]);
  const [schedules, setSchedules] = useState<EngineerSchedule[]>([]);
  const [rosterPatterns, setRosterPatterns] = useState<RosterPatternListItem[]>([]);
  const [currentRosterAssignment, setCurrentRosterAssignment] = useState<EngineerRosterAssignment | null>(null);
  
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [isSavingSchedules, setIsSavingSchedules] = useState(false);
  
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [selectedChangeTypeId, setSelectedChangeTypeId] = useState<number | null>(null);
  const [proficiencyLevel, setProficiencyLevel] = useState(1);

  const [showRosterDialog, setShowRosterDialog] = useState(false);
  const [selectedPatternId, setSelectedPatternId] = useState<number | null>(null);
  const [rosterStartDate, setRosterStartDate] = useState('');
  const [rosterEndDate, setRosterEndDate] = useState('');
  const [rosterIsRepeating, setRosterIsRepeating] = useState(true);

  const [showCloneDialog, setShowCloneDialog] = useState(false);
  const [sourceEngineerId, setSourceEngineerId] = useState<number | null>(null);
  const [allEngineers, setAllEngineers] = useState<Engineer[]>([]);

  useEffect(() => {
    if (user?.role !== 'admin') {
      navigate('/dashboard');
      return;
    }
    loadData();
  }, [id, user, navigate]);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [engineersData, skillsData, productsData, changeTypesData, schedulesData, patternsData, assignmentData] = await Promise.all([
        api.getEngineers(),
        api.getEngineerSkills(parseInt(id!)),
        api.getProducts(),
        api.getChangeTypes(),
        api.getEngineerSchedules(parseInt(id!)).catch(() => []),
        api.getRosterPatterns().catch(() => []),
        api.getEngineerRosterAssignment(parseInt(id!)).catch(() => null),
      ]);
      
      const engineers = engineersData as Engineer[];
      setAllEngineers(engineers);
      const foundEngineer = engineers.find(e => e.id === parseInt(id!));
      setEngineer(foundEngineer || null);
      setSkills(skillsData as EngineerSkill[]);
      setProducts(productsData as Product[]);
      setChangeTypes(changeTypesData as ChangeType[]);
      setRosterPatterns(patternsData as RosterPatternListItem[]);
      setCurrentRosterAssignment(assignmentData as EngineerRosterAssignment | null);
      
      const loadedSchedules = schedulesData as EngineerSchedule[];
      if (loadedSchedules.length > 0) {
        setSchedules(loadedSchedules);
      } else {
        setSchedules(DAY_NAMES.map((_, index) => ({
          day_of_week: index,
          is_working: index < 5,
          start_time: '09:00',
          end_time: '17:00',
        })));
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load data');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddSkill = async () => {
    if (!selectedProductId || !selectedChangeTypeId) return;
    
    try {
      await api.addEngineerSkill(parseInt(id!), selectedProductId, selectedChangeTypeId, proficiencyLevel);
      setShowAddDialog(false);
      setSelectedProductId(null);
      setSelectedChangeTypeId(null);
      setProficiencyLevel(1);
      loadData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleRemoveSkill = async (skillId: number) => {
    if (confirm('Are you sure you want to remove this skill?')) {
      try {
        await api.removeEngineerSkill(parseInt(id!), skillId);
        loadData();
      } catch (err: any) {
        setError(err.message);
      }
    }
  };

  const handleCloneSkills = async () => {
    if (!sourceEngineerId) return;
    
    try {
      await api.cloneEngineerSkills(parseInt(id!), sourceEngineerId);
      setShowCloneDialog(false);
      setSourceEngineerId(null);
      loadData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleToggleAvailability = async () => {
    if (!engineer) return;
    try {
      await api.updateEngineer(engineer.id, { is_available: !engineer.is_available });
      loadData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleScheduleChange = (dayIndex: number, field: keyof EngineerSchedule, value: any) => {
    setSchedules(prev => prev.map((schedule, idx) => 
      idx === dayIndex ? { ...schedule, [field]: value } : schedule
    ));
  };

  const handleSaveSchedules = async () => {
    setIsSavingSchedules(true);
    try {
      await api.updateEngineerSchedules(parseInt(id!), schedules);
      setError('');
    } catch (err: any) {
      setError(err.message || 'Failed to save schedules');
    } finally {
      setIsSavingSchedules(false);
    }
  };

  const handleAssignRoster = async () => {
    if (!selectedPatternId || !rosterStartDate) return;
    
    try {
      await api.assignRosterToEngineer(parseInt(id!), {
        pattern_id: selectedPatternId,
        start_date: rosterStartDate,
        end_date: rosterEndDate || undefined,
        is_repeating: rosterIsRepeating,
      });
      setShowRosterDialog(false);
      setSelectedPatternId(null);
      setRosterStartDate('');
      setRosterEndDate('');
      setRosterIsRepeating(true);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to assign roster pattern');
    }
  };

  const handleRemoveRosterAssignment = async () => {
    if (confirm('Are you sure you want to remove this roster assignment?')) {
      try {
        await api.removeEngineerRosterAssignment(parseInt(id!));
        setCurrentRosterAssignment(null);
        loadData();
      } catch (err: any) {
        setError(err.message || 'Failed to remove roster assignment');
      }
    }
  };

  const getPatternName = (patternId: number) => {
    const pattern = rosterPatterns.find(p => p.id === patternId);
    return pattern?.name || 'Unknown Pattern';
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-500">Loading engineer details...</p>
        </div>
      </div>
    );
  }

  if (!engineer) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Engineer Not Found</h2>
          <Button onClick={() => navigate('/admin')}>Return to Admin</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center py-4">
            <Button variant="ghost" onClick={() => navigate('/admin')} className="mr-4">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
            <div>
              <h1 className="text-xl font-semibold text-gray-900">Engineer Skills</h1>
              <p className="text-sm text-gray-500">Manage skills for {engineer.user?.full_name}</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg">
            {error}
            <button onClick={() => setError('')} className="ml-2 text-red-900 font-medium">Dismiss</button>
          </div>
        )}

        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Engineer Details</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <div className="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center mr-4">
                  <User className="w-6 h-6 text-indigo-600" />
                </div>
                <div>
                  <p className="font-medium text-lg">{engineer.user?.full_name}</p>
                  <p className="text-gray-500">{engineer.calendar_email}</p>
                  <p className="text-sm text-gray-400">
                    Working hours: {engineer.working_hours_start} - {engineer.working_hours_end}
                  </p>
                </div>
              </div>
              <div className="flex items-center space-x-4">
                <Badge className={engineer.is_available ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                  {engineer.is_available ? 'Available' : 'Unavailable'}
                </Badge>
                <Button variant="outline" onClick={handleToggleAvailability}>
                  {engineer.is_available ? 'Set Unavailable' : 'Set Available'}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Skills Matrix</CardTitle>
              <CardDescription>
                Define which products and change types this engineer can handle
              </CardDescription>
            </div>
            <div className="flex space-x-2">
              <Dialog open={showCloneDialog} onOpenChange={setShowCloneDialog}>
                <DialogTrigger asChild>
                  <Button variant="outline">
                    <Copy className="w-4 h-4 mr-2" />
                    Clone Skills
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Clone Skills from Another Engineer</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>Select Engineer to Clone From</Label>
                      <Select
                        value={sourceEngineerId?.toString() || ''}
                        onValueChange={(v) => setSourceEngineerId(parseInt(v))}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select engineer" />
                        </SelectTrigger>
                        <SelectContent>
                          {allEngineers
                            .filter(e => e.id !== parseInt(id!))
                            .map((e) => (
                              <SelectItem key={e.id} value={e.id.toString()}>
                                {e.user?.full_name || e.calendar_email}
                              </SelectItem>
                            ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <p className="text-sm text-gray-500">
                      This will copy all skills from the selected engineer to this engineer. 
                      Existing skills will not be duplicated.
                    </p>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setShowCloneDialog(false)}>Cancel</Button>
                    <Button onClick={handleCloneSkills} disabled={!sourceEngineerId}>
                      Clone Skills
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
              <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
                <DialogTrigger asChild>
                  <Button>
                    <Plus className="w-4 h-4 mr-2" />
                    Add Skill
                  </Button>
                </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add Skill</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Product</Label>
                    <Select
                      value={selectedProductId?.toString() || ''}
                      onValueChange={(v) => setSelectedProductId(parseInt(v))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select product" />
                      </SelectTrigger>
                      <SelectContent>
                        {products.map((p) => (
                          <SelectItem key={p.id} value={p.id.toString()}>
                            {p.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Change Type</Label>
                    <Select
                      value={selectedChangeTypeId?.toString() || ''}
                      onValueChange={(v) => setSelectedChangeTypeId(parseInt(v))}
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
                  <div className="space-y-2">
                    <Label>Proficiency Level (1-5)</Label>
                    <Select
                      value={proficiencyLevel.toString()}
                      onValueChange={(v) => setProficiencyLevel(parseInt(v))}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {[1, 2, 3, 4, 5].map((level) => (
                          <SelectItem key={level} value={level.toString()}>
                            {level} - {level === 1 ? 'Beginner' : level === 2 ? 'Basic' : level === 3 ? 'Intermediate' : level === 4 ? 'Advanced' : 'Expert'}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setShowAddDialog(false)}>Cancel</Button>
                  <Button onClick={handleAddSkill} disabled={!selectedProductId || !selectedChangeTypeId}>
                    Add Skill
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
            </div>
          </CardHeader>
          <CardContent>
            {skills.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-gray-500">No skills assigned yet</p>
                <p className="text-sm text-gray-400 mt-1">
                  Add skills to allow this engineer to be booked for specific products and change types
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Product</TableHead>
                    <TableHead>Change Type</TableHead>
                    <TableHead>Proficiency</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {skills.map((skill) => (
                    <TableRow key={skill.id}>
                      <TableCell className="font-medium">{skill.product?.name || 'Unknown'}</TableCell>
                      <TableCell>{skill.change_type?.name || 'Unknown'}</TableCell>
                      <TableCell>
                        <div className="flex items-center">
                          {[1, 2, 3, 4, 5].map((level) => (
                            <div
                              key={level}
                              className={`w-2 h-4 mr-1 rounded ${
                                level <= skill.proficiency_level ? 'bg-indigo-600' : 'bg-gray-200'
                              }`}
                            />
                          ))}
                          <span className="ml-2 text-sm text-gray-500">
                            {skill.proficiency_level}/5
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveSkill(skill.id)}
                        >
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

        <Card className="mt-6">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center">
                <Calendar className="w-5 h-5 mr-2" />
                Working Schedule
              </CardTitle>
              <CardDescription>
                Configure working hours for each day of the week
              </CardDescription>
            </div>
            <Button onClick={handleSaveSchedules} disabled={isSavingSchedules}>
              {isSavingSchedules ? 'Saving...' : 'Save Schedule'}
            </Button>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {schedules.map((schedule, index) => (
                <div key={index} className="flex items-center space-x-4 p-3 bg-gray-50 rounded-lg">
                  <div className="w-28 font-medium">{DAY_NAMES[schedule.day_of_week]}</div>
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id={`working-${index}`}
                      checked={schedule.is_working}
                      onChange={(e) => handleScheduleChange(index, 'is_working', e.target.checked)}
                      className="w-4 h-4"
                    />
                    <Label htmlFor={`working-${index}`} className="text-sm">
                      Working
                    </Label>
                  </div>
                  {schedule.is_working && (
                    <>
                      <div className="flex items-center space-x-2">
                        <Clock className="w-4 h-4 text-gray-400" />
                        <Input
                          type="time"
                          value={schedule.start_time}
                          onChange={(e) => handleScheduleChange(index, 'start_time', e.target.value)}
                          className="w-32"
                        />
                      </div>
                      <span className="text-gray-400">to</span>
                      <Input
                        type="time"
                        value={schedule.end_time}
                        onChange={(e) => handleScheduleChange(index, 'end_time', e.target.value)}
                        className="w-32"
                      />
                    </>
                  )}
                  {!schedule.is_working && (
                    <span className="text-gray-400 italic">Not working</span>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="mt-6">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center">
                <CalendarDays className="w-5 h-5 mr-2" />
                Roster Pattern Assignment
              </CardTitle>
              <CardDescription>
                Assign a roster pattern to define complex shift schedules
              </CardDescription>
            </div>
            {!currentRosterAssignment && (
              <Dialog open={showRosterDialog} onOpenChange={setShowRosterDialog}>
                <DialogTrigger asChild>
                  <Button>
                    <Plus className="w-4 h-4 mr-2" />
                    Assign Pattern
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Assign Roster Pattern</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>Roster Pattern</Label>
                      <Select
                        value={selectedPatternId?.toString() || ''}
                        onValueChange={(v) => setSelectedPatternId(parseInt(v))}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select a pattern" />
                        </SelectTrigger>
                        <SelectContent>
                          {rosterPatterns.filter(p => p.is_active).map((pattern) => (
                            <SelectItem key={pattern.id} value={pattern.id.toString()}>
                              {pattern.name} ({pattern.phase_count} phase{pattern.phase_count !== 1 ? 's' : ''})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {rosterPatterns.length === 0 && (
                        <p className="text-sm text-gray-500">
                          No roster patterns available. Create one in Admin &gt; Rosters first.
                        </p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Label>Start Date</Label>
                      <Input
                        type="date"
                        value={rosterStartDate}
                        onChange={(e) => setRosterStartDate(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>End Date (optional)</Label>
                      <Input
                        type="date"
                        value={rosterEndDate}
                        onChange={(e) => setRosterEndDate(e.target.value)}
                      />
                      <p className="text-xs text-gray-500">
                        Leave empty for continuous pattern
                      </p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id="is-repeating"
                        checked={rosterIsRepeating}
                        onChange={(e) => setRosterIsRepeating(e.target.checked)}
                        className="w-4 h-4"
                      />
                      <Label htmlFor="is-repeating">
                        Repeat pattern continuously
                      </Label>
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setShowRosterDialog(false)}>Cancel</Button>
                    <Button onClick={handleAssignRoster} disabled={!selectedPatternId || !rosterStartDate}>
                      Assign Pattern
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
          </CardHeader>
          <CardContent>
            {currentRosterAssignment ? (
              <div className="p-4 bg-indigo-50 rounded-lg">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-lg text-indigo-900">
                      {getPatternName(currentRosterAssignment.pattern_id)}
                    </p>
                    <div className="mt-2 space-y-1 text-sm text-indigo-700">
                      <p>
                        <span className="font-medium">Start Date:</span>{' '}
                        {new Date(currentRosterAssignment.start_date).toLocaleDateString()}
                      </p>
                      {currentRosterAssignment.end_date && (
                        <p>
                          <span className="font-medium">End Date:</span>{' '}
                          {new Date(currentRosterAssignment.end_date).toLocaleDateString()}
                        </p>
                      )}
                      <p>
                        <span className="font-medium">Repeating:</span>{' '}
                        {currentRosterAssignment.is_repeating ? 'Yes' : 'No'}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRemoveRosterAssignment}
                    className="text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Remove
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-center py-8">
                <p className="text-gray-500">No roster pattern assigned</p>
                <p className="text-sm text-gray-400 mt-1">
                  Assign a roster pattern to define when this engineer is available based on complex shift schedules
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
