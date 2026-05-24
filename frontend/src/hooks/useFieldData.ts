import { useQuery } from '@tanstack/react-query';
import api from '../services/api';

interface FieldStats {
  activeEnumerators: number;
  surveysToday: number;
  photosToday: number;
  pendingSync: number;
  whatsappActive: number;
  whatsappMessages: number;
  supportTickets: number;
}

interface Enumerator {
  id: string;
  name: string;
  phone: string;
  surveys: number;
  qualityScore: number;
  rejectionRate: number;
  lastSync: string;
  lastSyncMinutes: number;
}

const MOCK_STATS: FieldStats = {
  activeEnumerators: 12,
  surveysToday: 156,
  photosToday: 420,
  pendingSync: 23,
  whatsappActive: 8,
  whatsappMessages: 342,
  supportTickets: 3,
};

const MOCK_ENUMERATORS: Enumerator[] = [
  { id: '1', name: 'John Mwangi', phone: '+254712345678', surveys: 45, qualityScore: 96, rejectionRate: 2, lastSync: '10 min ago', lastSyncMinutes: 10 },
  { id: '2', name: 'Amina Ochieng', phone: '+254723456789', surveys: 38, qualityScore: 94, rejectionRate: 4, lastSync: '25 min ago', lastSyncMinutes: 25 },
  { id: '3', name: 'Peter Njoroge', phone: '+254734567890', surveys: 12, qualityScore: 78, rejectionRate: 18, lastSync: '3 hours ago', lastSyncMinutes: 180 },
  { id: '4', name: 'Grace Wanjiku', phone: '+254745678901', surveys: 52, qualityScore: 98, rejectionRate: 1, lastSync: '5 min ago', lastSyncMinutes: 5 },
  { id: '5', name: 'David Kimani', phone: '+254756789012', surveys: 9, qualityScore: 85, rejectionRate: 8, lastSync: '1 hour ago', lastSyncMinutes: 60 },
];

export function useFieldData() {
  const { data: stats, isLoading: statsLoading } = useQuery<FieldStats>({
    queryKey: ['fieldStats'],
    queryFn: async () => {
      // In production: const res = await api.get('/field/stats'); return res.data;
      return MOCK_STATS;
    },
  });

  const { data: enumerators, isLoading: enumLoading } = useQuery<Enumerator[]>({
    queryKey: ['enumerators'],
    queryFn: async () => {
      // In production: const res = await api.get('/webhooks/enumerators'); return res.data;
      return MOCK_ENUMERATORS;
    },
  });

  return {
    stats: stats || MOCK_STATS,
    enumerators: enumerators || MOCK_ENUMERATORS,
    loading: statsLoading || enumLoading,
  };
}
