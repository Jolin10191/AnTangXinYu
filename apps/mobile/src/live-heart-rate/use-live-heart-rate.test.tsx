import { useEffect } from 'react';
import { AppState, type AppStateStatus } from 'react-native';
import { act, create, type ReactTestRenderer } from 'react-test-renderer';
import { useLiveHeartRate, type LiveHeartRateController } from './use-live-heart-rate';

const mockDisconnect = jest.fn().mockResolvedValue(undefined);
const mockRemove = jest.fn();
const mockListeners: Record<string, (event: unknown) => void> = {};
jest.mock('../../modules/live-heart-rate', () => ({
  isLiveHeartRateAvailable: () => true,
  addLiveHeartRateListener: (name: string, listener: (event: unknown) => void) => {
    mockListeners[name] = listener;
    return { remove: mockRemove };
  },
  disconnectLiveHeartRate: () => mockDisconnect(),
}));

let controller: LiveHeartRateController;
function Probe() {
  const current = useLiveHeartRate(true);
  useEffect(() => { controller = current; }, [current]);
  return null;
}

test('clears live samples on background and disconnects on account unmount', async () => {
  let onState: ((state: AppStateStatus) => void) | undefined;
  const stateRemove = jest.fn();
  const spy = jest.spyOn(AppState, 'addEventListener').mockImplementation((_event, callback) => {
    onState = callback;
    return { remove: stateRemove };
  });
  let tree: ReactTestRenderer;
  await act(async () => { tree = create(<Probe />); });
  act(() => mockListeners.onSample({ beatsPerMinute: 78, measuredAt: Date.now(), name: '手环' }));
  expect(controller.latest?.beatsPerMinute).toBe(78);
  await act(async () => { onState!('background'); });
  expect(controller.latest).toBeNull();
  expect(mockDisconnect).toHaveBeenCalledTimes(1);
  await act(async () => tree!.unmount());
  expect(mockDisconnect).toHaveBeenCalledTimes(2);
  expect(mockRemove).toHaveBeenCalledTimes(3);
  expect(stateRemove).toHaveBeenCalledTimes(1);
  spy.mockRestore();
});
