export type Track = {
  id: number;
  trackName: string;
  stateId: number;
  stateName: string | null;
  isArchived: boolean;
};

export type StateOption = {
  id: number;
  stateName: string;
  countryName: string;
};

export type AdminScope = {
  isGlobal: boolean;
  trackIds: number[] | null;
};

export type ApiResponse<T> = {
  msg: string;
  data: T;
};
