import {createContext, useState, useEffect} from 'react';
import EncryptedStorage from 'react-native-encrypted-storage';
import axios from 'axios';
import {BACKEND_URL} from '@env';

export const MomentsContext = createContext();

export const MomentsProvider = ({children}) => {
  const [moments, setMoments] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const logError = (message, error) => {
    console.error(message, error);
  };

  const updateLocalStorage = async data => {
    try {
      await EncryptedStorage.setItem('moments', JSON.stringify(data));
    } catch (error) {
      logError('Failed to update local storage:', error);
      throw new Error('Error saving data');
    }
  };

  const fetchMomentsFromLocalStorage = async () => {
    try {
      const momentsJson = await EncryptedStorage.getItem('moments');
      return momentsJson ? JSON.parse(momentsJson) : null;
    } catch (error) {
      logError('Failed to retrieve moments from local storage:', error);
      return null;
    }
  };

  const fetchMoments = async () => {
    setIsLoading(true);
    let momentsData = (await fetchMomentsFromLocalStorage()) || [];

    if (momentsData.length === 0) {
      try {
        const response = await axios.get(`${BACKEND_URL}:30000/moments`);
        if (response.status === 200 && response.data) {
          momentsData = response.data.moments;
          await updateLocalStorage(momentsData);
        } else {
          console.log(
            'Request succeeded but with a non-200 status code:',
            response.status,
          );
        }
      } catch (error) {
        logError('Request failed:', error);
      }
    }

    setMoments(momentsData);
    setIsLoading(false);
  };

  const addMoment = async moment => {
    try {
      const response = await axios.post(`${BACKEND_URL}:30000/moments`, {
        newMoment: moment,
      });
      if (response.status === 200 && response.data) {
        moment.id = response.data.id;
        const moments = (await fetchMomentsFromLocalStorage()) || [];
        moments.push(moment);
        await updateLocalStorage(moments);
        setMoments(moments);
      } else {
        console.log(
          'Request succeeded but with a non-200 status code:',
          response.status,
        );
      }
    } catch (error) {
      logError('Error managing local storage for moments:', error);
    }
  };

  const deleteMoment = async moment => {
    try {
      const response = await axios.delete(`${BACKEND_URL}:30000/moments`, {
        data: {id: moment.id},
      });
      if (response.status === 200) {
        let moments = (await fetchMomentsFromLocalStorage()) || [];
        moments = moments.filter(item => item.id !== moment.id);
        await updateLocalStorage(moments);
        setMoments(moments);
      }
    } catch (error) {
      logError('Error deleting moment:', error);
    }
  };

  useEffect(() => {
    fetchMoments();
  }, []);

  return (
    <MomentsContext.Provider
      value={{
        moments,
        setMoments,
        isLoading,
        fetchMoments,
        deleteMoment,
        addMoment,
      }}>
      {children}
    </MomentsContext.Provider>
  );
};
