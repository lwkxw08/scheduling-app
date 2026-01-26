import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { RosterPatternListItem, RosterPattern } from '../types';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Badge } from './ui/badge';
import { Plus, Edit, Trash2, Clock, CalendarDays, ArrowUp, ArrowDown } from 'lucide-react';

interface PhaseInput {
  id?: number;
  phase_order: number;
  name: string;
  days_on: number;
  days_off: number;
  start_time: string;
  end_time: string;
  repeat_weeks: number | null;
}

export default function RosterPatternBuilder() {
  const [patterns, setPatterns] = useState<RosterPatternListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const [showPatternDialog, setShowPatternDialog] = useState(false);
  const [editingPattern, setEditingPattern] = useState<RosterPattern | null>(null);
  const [patternName, setPatternName] = useState('');
  const [patternDescription, setPatternDescription] = useState('');
  const [phases, setPhases] = useState<PhaseInput[]>([]);

  useEffect(() => {
    loadPatterns();
  }, []);

  const loadPatterns = async () => {
    setIsLoading(true);
    try {
      const data = await api.getRosterPatterns();
      setPatterns(data as RosterPatternListItem[]);
    } catch (err: any) {
      setError(err.message || 'Failed to load roster patterns');
    } finally {
      setIsLoading(false);
    }
  };

  const resetForm = () => {
    setEditingPattern(null);
    setPatternName('');
    setPatternDescription('');
    setPhases([{
      phase_order: 1,
      name: 'Phase 1',
      days_on: 3,
      days_off: 4,
      start_time: '09:00',
      end_time: '17:00',
      repeat_weeks: null,
    }]);
  };

  const openEditPattern = async (patternId: number) => {
    try {
      const pattern = await api.getRosterPattern(patternId) as RosterPattern;
      setEditingPattern(pattern);
      setPatternName(pattern.name);
      setPatternDescription(pattern.description || '');
      setPhases(pattern.phases.map(p => ({
        id: p.id,
        phase_order: p.phase_order,
        name: p.name || `Phase ${p.phase_order}`,
        days_on: p.days_on,
        days_off: p.days_off,
        start_time: p.start_time,
        end_time: p.end_time,
        repeat_weeks: p.repeat_weeks,
      })));
      setShowPatternDialog(true);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleSavePattern = async () => {
    try {
      const data = {
        name: patternName,
        description: patternDescription || undefined,
        phases: phases.map((p, idx) => ({
          phase_order: idx + 1,
          name: p.name || undefined,
          days_on: p.days_on,
          days_off: p.days_off,
          start_time: p.start_time,
          end_time: p.end_time,
          repeat_weeks: p.repeat_weeks || undefined,
        })),
      };

      if (editingPattern) {
        await api.updateRosterPattern(editingPattern.id, data);
      } else {
        await api.createRosterPattern(data);
      }
      setShowPatternDialog(false);
      resetForm();
      loadPatterns();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeletePattern = async (id: number) => {
    if (confirm('Are you sure you want to delete this roster pattern?')) {
      try {
        await api.deleteRosterPattern(id);
        loadPatterns();
      } catch (err: any) {
        setError(err.message);
      }
    }
  };

  const addPhase = () => {
    setPhases([...phases, {
      phase_order: phases.length + 1,
      name: `Phase ${phases.length + 1}`,
      days_on: 3,
      days_off: 4,
      start_time: '09:00',
      end_time: '17:00',
      repeat_weeks: null,
    }]);
  };

  const removePhase = (index: number) => {
    if (phases.length > 1) {
      const newPhases = phases.filter((_, i) => i !== index);
      setPhases(newPhases.map((p, i) => ({ ...p, phase_order: i + 1 })));
    }
  };

  const updatePhase = (index: number, field: keyof PhaseInput, value: any) => {
    const newPhases = [...phases];
    newPhases[index] = { ...newPhases[index], [field]: value };
    setPhases(newPhases);
  };

  const movePhase = (index: number, direction: 'up' | 'down') => {
    if (direction === 'up' && index > 0) {
      const newPhases = [...phases];
      [newPhases[index - 1], newPhases[index]] = [newPhases[index], newPhases[index - 1]];
      setPhases(newPhases.map((p, i) => ({ ...p, phase_order: i + 1 })));
    } else if (direction === 'down' && index < phases.length - 1) {
      const newPhases = [...phases];
      [newPhases[index], newPhases[index + 1]] = [newPhases[index + 1], newPhases[index]];
      setPhases(newPhases.map((p, i) => ({ ...p, phase_order: i + 1 })));
    }
  };

  const formatPatternSummary = (pattern: RosterPatternListItem) => {
    return `${pattern.phase_count} phase${pattern.phase_count !== 1 ? 's' : ''}`;
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Roster Patterns</CardTitle>
          <CardDescription>
            Create complex shift patterns that can be assigned to engineers
          </CardDescription>
        </div>
        <Dialog open={showPatternDialog} onOpenChange={(open) => {
          setShowPatternDialog(open);
          if (!open) resetForm();
        }}>
          <DialogTrigger asChild>
            <Button onClick={resetForm}>
              <Plus className="w-4 h-4 mr-2" />
              Create Pattern
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{editingPattern ? 'Edit Roster Pattern' : 'Create Roster Pattern'}</DialogTitle>
              <DialogDescription>
                Define a pattern with multiple phases. Each phase specifies days on, days off, and working hours.
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Pattern Name</Label>
                  <Input 
                    value={patternName} 
                    onChange={(e) => setPatternName(e.target.value)}
                    placeholder="e.g., 3 on 4 off rotating"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Description (optional)</Label>
                  <Input 
                    value={patternDescription} 
                    onChange={(e) => setPatternDescription(e.target.value)}
                    placeholder="e.g., Day/Night rotation pattern"
                  />
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label className="text-base font-semibold">Phases</Label>
                  <Button type="button" variant="outline" size="sm" onClick={addPhase}>
                    <Plus className="w-4 h-4 mr-1" />
                    Add Phase
                  </Button>
                </div>

                {phases.map((phase, index) => (
                  <Card key={index} className="border-2">
                    <CardHeader className="py-3 px-4 bg-gray-50">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">Phase {index + 1}</Badge>
                          <Input
                            value={phase.name}
                            onChange={(e) => updatePhase(index, 'name', e.target.value)}
                            className="w-40 h-8"
                            placeholder="Phase name"
                          />
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => movePhase(index, 'up')}
                            disabled={index === 0}
                          >
                            <ArrowUp className="w-4 h-4" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => movePhase(index, 'down')}
                            disabled={index === phases.length - 1}
                          >
                            <ArrowDown className="w-4 h-4" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => removePhase(index)}
                            disabled={phases.length === 1}
                          >
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="py-4 px-4">
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <div className="space-y-2">
                          <Label className="text-xs text-gray-500">Days On</Label>
                          <Input
                            type="number"
                            min="1"
                            value={phase.days_on}
                            onChange={(e) => updatePhase(index, 'days_on', parseInt(e.target.value) || 1)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs text-gray-500">Days Off</Label>
                          <Input
                            type="number"
                            min="0"
                            value={phase.days_off}
                            onChange={(e) => updatePhase(index, 'days_off', parseInt(e.target.value) || 0)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs text-gray-500">Start Time</Label>
                          <Input
                            type="time"
                            value={phase.start_time}
                            onChange={(e) => updatePhase(index, 'start_time', e.target.value)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs text-gray-500">End Time</Label>
                          <Input
                            type="time"
                            value={phase.end_time}
                            onChange={(e) => updatePhase(index, 'end_time', e.target.value)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs text-gray-500">Repeat (weeks)</Label>
                          <Input
                            type="number"
                            min="1"
                            placeholder="Continuous"
                            value={phase.repeat_weeks || ''}
                            onChange={(e) => updatePhase(index, 'repeat_weeks', e.target.value ? parseInt(e.target.value) : null)}
                          />
                        </div>
                      </div>
                      <div className="mt-3 text-sm text-gray-500">
                        <Clock className="w-4 h-4 inline mr-1" />
                        {phase.days_on} day{phase.days_on !== 1 ? 's' : ''} working ({phase.start_time} - {phase.end_time}), 
                        then {phase.days_off} day{phase.days_off !== 1 ? 's' : ''} off
                        {phase.repeat_weeks ? ` for ${phase.repeat_weeks} week${phase.repeat_weeks !== 1 ? 's' : ''}` : ' (continuous)'}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {phases.length > 1 && (
                <div className="p-4 bg-blue-50 rounded-lg">
                  <h4 className="font-medium text-blue-900 mb-2">Pattern Summary</h4>
                  <p className="text-sm text-blue-700">
                    This pattern has {phases.length} phases that will cycle in order:
                  </p>
                  <ul className="mt-2 text-sm text-blue-700 list-disc list-inside">
                    {phases.map((phase, index) => (
                      <li key={index}>
                        <strong>{phase.name || `Phase ${index + 1}`}:</strong> {phase.days_on} days on ({phase.start_time}-{phase.end_time}), {phase.days_off} days off
                        {phase.repeat_weeks ? ` - repeats for ${phase.repeat_weeks} weeks` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setShowPatternDialog(false)}>Cancel</Button>
              <Button onClick={handleSavePattern} disabled={!patternName || phases.length === 0}>
                {editingPattern ? 'Update Pattern' : 'Create Pattern'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardHeader>

      <CardContent>
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg">
            {error}
            <button onClick={() => setError('')} className="ml-2 text-red-900 font-medium">Dismiss</button>
          </div>
        )}

        {patterns.length === 0 ? (
          <div className="text-center py-12">
            <CalendarDays className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No roster patterns created yet</h3>
            <p className="text-gray-500 mb-4">
              Create patterns to define complex shift schedules for your engineers
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Phases</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {patterns.map((pattern) => (
                <TableRow key={pattern.id}>
                  <TableCell className="font-medium">{pattern.name}</TableCell>
                  <TableCell>{pattern.description || '-'}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{formatPatternSummary(pattern)}</Badge>
                  </TableCell>
                  <TableCell>{new Date(pattern.created_at).toLocaleDateString()}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditPattern(pattern.id)}
                    >
                      <Edit className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeletePattern(pattern.id)}
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
  );
}
